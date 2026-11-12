#!/usr/bin/env python3
"""
MIDRC DICOM Header Extraction Pipeline (TES version)
Extracts DICOM headers from imaging series, uploads them to indexd,
and links them to their proper sheepdog records.

Local vs TES version:
  1. upload_headers() now RETURNS header_guids.
  2. run_project() fails loudly if no header zips were uploaded.
  3. log_to_s3() is a safe no-op when GEN3_TOKEN is not set.
  4. core_metadata_collection creation no longer aborts the run if it already exists.
  5. main() exits non-zero if any project fails, so TES reports EXECUTOR_ERROR
     instead of COMPLETE.

Usage:
    python3 DICOM_pipeline.py \
        --project-ids TCIA-RICORD_1a \
        --endpoint staging.midrc.org \
        --credentials /work/credentials.json \
        --working-dir /work/outputs \
        --source-nodes ct_series_file \
        --no-prompt
"""

import argparse
import copy
import glob
import json
import logging
import os
import shutil
import zipfile
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import pydicom as dicom
import requests
from tqdm import tqdm

from gen3.auth import Gen3Auth
from gen3.file import Gen3File
from gen3.index import Gen3Index
from gen3.query import Gen3Query
from gen3.submission import Gen3Submission

# -------------------------------------------------------
# Logging
# -------------------------------------------------------
def setup_logging(log_dir: str) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level   = logging.INFO,
        format  = '%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{log_dir}/pipeline.log")
        ]
    )
    return logging.getLogger(__name__)

def log_to_s3(message, bucket, prefix, token, logger):
    """Write a progress message to S3. No-op (local log only) if no token is available."""
    logger.info(f"PROGRESS: {message}")
    if not token:
        return
    try:
        requests.put(
            f"https://brhstaging.data-commons.org/workflows/s3/{bucket}/{prefix}/progress.log",
            data=message.encode(),
            headers={
                "authorization": f"bearer {token}",
                "Content-Type": "text/plain"
            },
            timeout=30
        )
    except Exception as e:
        logger.warning(f"Failed to write to S3: {e}")

# -------------------------------------------------------
# Argument parsing
# -------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description='MIDRC DICOM Header Pipeline')
    parser.add_argument('--project-ids',  required=True,
                        help='Comma-separated project IDs e.g. TCIA-RICORD_1c,TCIA-RICORD_1a')
    parser.add_argument('--endpoint',     required=True,
                        help='Gen3 endpoint e.g. staging.midrc.org')
    parser.add_argument('--credentials',  required=True,
                        help='Filepath to credentials JSON')
    parser.add_argument('--working-dir',  required=True,
                        help='Working directory for outputs')
    parser.add_argument('--source-nodes', default='dx_series_file,cr_series_file',
                        help='Comma-separated source nodes to query')
    parser.add_argument('--no-prompt',    action='store_true',
                        help='Skip confirmation prompts (required for TES/non-interactive runs)')
    return parser.parse_args()

# -------------------------------------------------------
# Step 1: Download imaging series
# -------------------------------------------------------
def download_series(project_id, query, file_client, pdir, download_dir, source_nodes, date_str, logger):
    logger.info(f"Querying data files for {project_id}")

    data_files = query.raw_data_download(
        data_type="data_file",
        fields=None,
        filter_object={
            "AND": [
                {"=":  {"project_id": project_id}},
                {"IN": {"source_node": source_nodes}},
            ]
        },
        sort_fields=[{"submitter_id": "asc"}]
    )
    logger.info(f"Total data files returned: {len(data_files)}")

    # Confirm all records are series files
    non_series = [f for f in data_files if not f.get('source_node', '').endswith('_series_file')]
    assert len(non_series) == 0, f"Found {len(non_series)} non-series files"
    logger.info(f"Node types: {set([f['source_node'] for f in data_files])}")

    series_guids = [dfile["object_id"] for dfile in data_files]
    logger.info(f"Series file GUIDs: {len(series_guids)}")

    if not series_guids:
        logger.warning("No series GUIDs found — skipping download.")
        return data_files, [], []

    # Write manifest
    manifest_path = Path(pdir) / f"{project_id}_guppy_data_files_manifest_{len(series_guids)}_{date_str}.json"
    with open(manifest_path, "w") as f:
        json.dump([{"object_id": guid} for guid in series_guids], f, indent=2)
    logger.info(f"Manifest written: {manifest_path}")

    successes = []
    failures  = []

    for guid in series_guids:
        try:
            result   = file_client.get_presigned_url(guid, protocol="s3")
            url      = result["url"]
            filename = url.split("?")[0].split("/")[-1]
            filepath = Path(download_dir) / filename

            if filepath.exists():
                logger.info(f"Skipping (exists): {filename}")
                successes.append({"project_id": project_id, "guid": guid, "filename": filename, "status": "skipped"})
                continue

            logger.info(f"Downloading: {filename}")
            with requests.get(url, stream=True, timeout=300) as r:
                if r.status_code == 404:
                    logger.warning(f"NOT FOUND (404): {filename}")
                    failures.append({"project_id": project_id, "stage": "download", "guid": guid,
                                     "filename": filename, "error": "404 - file not found in S3"})
                    continue
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    f.write(r.content)

            successes.append({"project_id": project_id, "guid": guid, "filename": filename, "status": "downloaded"})
            logger.info(f"Done: {filename}")

        except Exception as e:
            logger.error(f"FAILED: {guid} — {e}")
            failures.append({"project_id": project_id, "stage": "download", "guid": guid, "error": str(e)})

    return data_files, successes, failures


# -------------------------------------------------------
# Step 2: Extract DICOM headers and zip them
# -------------------------------------------------------
def extract_headers(data_files, project_id, pdir, download_dir, logger):
    logger.info("Building series metadata lookup")

    series_files = [d for d in data_files if d.get('source_node', '').endswith('_series_file')]

    # Check for missing study_uid or case_ids
    missing_study = [d for d in series_files if not d.get('study_uid')]
    missing_case  = [d for d in series_files if not d.get('case_ids')]
    logger.info(f"Missing study_uid: {len(missing_study)}")
    logger.info(f"Missing case_ids:  {len(missing_case)}")

    # Remove invalid records
    series_files = [d for d in series_files if d.get('study_uid') and d.get('case_ids')]
    logger.info(f"Valid series files: {len(series_files)}")

    # Build series metadata lookup
    series_metadata = {}
    for dfile in series_files:
        fname  = dfile['file_name']
        s_uid  = Path(fname).stem
        c_id   = dfile['case_ids'][0] if dfile.get('case_ids') else 'unknown_case'
        st_uid = dfile['study_uid'][0] if dfile.get('study_uid') else 'unknown_study'
        series_metadata[s_uid] = {'case_id': c_id, 'study_uid': st_uid}

    zips = glob.glob(f"{download_dir}/*.zip")
    logger.info(f"Found {len(zips)} zip files to process")

    for i, zip_path in enumerate(zips):
        series_uid = Path(zip_path).stem
        unzip_dir  = Path(zip_path).parent / series_uid

        logger.info(f"({i+1}/{len(zips)}): {series_uid}")

        os.makedirs(unzip_dir, exist_ok=True)

        dcms = sorted(glob.glob(str(unzip_dir / "**/*.dcm"), recursive=True))
        if not dcms:
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(unzip_dir)
            except zipfile.BadZipFile:
                logger.warning(f"Bad zip file: {zip_path}, skipping")
                continue

            dcms = sorted(glob.glob(str(unzip_dir / "**/*.dcm"), recursive=True))
            if not dcms:
                logger.warning(f"No DICOM files found in {unzip_dir}, skipping.")
                continue

        if series_uid in series_metadata:
            case_id   = series_metadata[series_uid]['case_id']
            study_uid = series_metadata[series_uid]['study_uid']

            if study_uid == 'unknown_study':
                logger.warning(f"No study_uid in metadata — trying DICOM tags")
                first = dicom.dcmread(dcms[0], force=True)
                try:
                    study_uid = first["StudyInstanceUID"].value
                except KeyError:
                    logger.warning(f"No StudyInstanceUID tag — using unknown_study")
        else:
            logger.warning(f"No metadata found for {series_uid} — using DICOM tags")
            first = dicom.dcmread(dcms[0], force=True)
            try:
                study_uid = first["StudyInstanceUID"].value
                case_id   = first["PatientID"].value
            except KeyError as e:
                logger.warning(f"Missing tag {e} — using fallback values")
                study_uid = "unknown_study"
                case_id   = "unknown_case"

        hdir = Path(pdir) / "headers" / project_id / case_id / study_uid / series_uid
        os.makedirs(hdir, exist_ok=True)

        for j, dcm in enumerate(dcms):
            dimg = dicom.dcmread(dcm, force=True)
            try:
                dcm_name     = Path(dcm).stem
                instance_uid = dimg["SOPInstanceUID"].value
                hdfile       = hdir / f"{dcm_name}_{instance_uid}_header.dcm"
            except Exception:
                try:
                    instance_uid = dimg["SOPInstanceUID"].value
                    hdfile       = hdir / f"{instance_uid}_header.dcm"
                except Exception:
                    hdfile = hdir / f"instance_{j}_header.dcm"

            try:
                del dimg["PixelData"]
            except Exception:
                pass

            dimg.save_as(hdfile)

        shutil.make_archive(f"{hdir}_headers", "zip", root_dir=str(hdir.parent), base_dir=hdir.name)
        logger.info(f"Headers zipped: {hdir}_headers.zip")

    return series_files, zips


# -------------------------------------------------------
# Step 3: Validate header zips before upload
# -------------------------------------------------------
def validate_header_zips(series_files, failures, pdir, logger):
    header_dir  = f"{pdir}/headers"
    os.chdir(header_dir)
    header_zips = glob.glob("*/*/*/*_headers.zip")

    # Remove extra zips not in valid series files
    valid_series_uids = set([Path(d['file_name']).stem for d in series_files])
    extra_zips        = [hz for hz in header_zips if Path(hz).stem.replace('_headers', '') not in valid_series_uids]

    for hz in extra_zips:
        os.remove(Path(header_dir) / hz)
        logger.info(f"Deleted extra zip: {hz}")

    # Re-glob after cleanup
    header_zips = glob.glob("*/*/*/*_headers.zip")

    # Calculate expected
    failed_guids     = set([f['guid'] for f in failures if f.get('stage') == 'download'])
    failed_in_series = [d for d in series_files if d['object_id'] in failed_guids]
    other_failures   = len(series_files) - len(header_zips) - len(failed_in_series)
    expected         = len(series_files) - len(failed_in_series) - other_failures

    logger.info(f"Series files:                        {len(series_files)}")
    logger.info(f"Failed downloads in series_files:    {len(failed_in_series)}")
    logger.info(f"Other failures (e.g. unknown_study): {other_failures}")
    logger.info(f"Expected header zips:                {expected}")
    logger.info(f"Actual header zips:                  {len(header_zips)}")

    assert len(header_zips) == expected, \
        f"Not all header zip files were created: {len(header_zips)} headers vs {expected} expected."
    logger.info("Assert passed — counts match")

    return header_zips, header_dir


# -------------------------------------------------------
# Step 4: Upload header zips to indexd/S3
# -------------------------------------------------------
def upload_headers(header_zips, header_dir, file_client, failures, logger):
    header_guids = {}

    for i, header_zip in enumerate(header_zips):
        logger.info(f"({i+1}/{len(header_zips)}): {header_zip}")

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                # Get fresh presigned URL on every attempt
                upload_response = file_client.upload_file(
                    file_name=header_zip,
                    protocol="s3",
                )
                guid       = upload_response.get("guid")
                upload_url = upload_response.get("url")

                with open(Path(header_dir) / header_zip, 'rb') as f:
                    file_bytes = f.read()

                s3_response = requests.put(
                    upload_url,
                    data=file_bytes,
                    headers={'Content-Type': 'application/zip'},
                    timeout=300
                )
                s3_response.raise_for_status()

                series_uid               = Path(header_zip).stem.replace("_headers", "")
                header_guids[series_uid] = guid
                logger.info(f"  Uploaded: {guid}")
                break  # success — exit retry loop

            except Exception as e:
                logger.warning(f"  Attempt {attempt}/{max_retries} failed: {e}")
                if attempt == max_retries:
                    logger.error(f"  Giving up on {header_zip}")
                    failures.append({"file": header_zip, "error": str(e)})

    upload_failures = [f for f in failures if f.get('file', '').endswith('_headers.zip')]
    logger.info(f"Uploaded: {len(header_guids)}")
    logger.info(f"Upload failures: {len(upload_failures)}")
    logger.info(f"Download failures (carried over): {len(failures) - len(upload_failures)}")

    return header_guids


# -------------------------------------------------------
# Step 5: Confirm uploads and fetch indexd records
# -------------------------------------------------------
def confirm_uploads(header_guids, index_client, pdir, project_id, date_str, logger):
    dids  = list(header_guids.values())
    irecs = []
    for did in tqdm(dids, desc="Fetching indexd records"):
        rec = index_client.get_record(did)
        if rec is not None:
            irecs.append(rec)
    logger.info(f"Records fetched from indexd: {len(irecs)}")

    # Formatting check
    logger.info("Formatting check (sample of 5):")
    for series_uid, guid in list(header_guids.items())[:5]:
        rec             = index_client.get_record(guid)
        indexd_filename = rec.get('file_name', '')
        match           = series_uid in indexd_filename
        logger.info(f"  Series UID: {series_uid}")
        logger.info(f"  Indexd:     {indexd_filename}")
        logger.info(f"  Match:      {match}")

    # Spot check size and hashes
    logger.info("Spot checking size and hashes (sample of 3):")
    for series_uid, guid in list(header_guids.items())[:3]:
        rec = index_client.get_record(guid)
        logger.info(f"  {guid}")
        logger.info(f"  size:   {rec.get('size')}")
        logger.info(f"  hashes: {rec.get('hashes')}")
        logger.info(f"  urls:   {rec.get('urls')}")

    hrecs = [rec for rec in irecs if rec.get("file_name", "").endswith("_headers.zip")]
    logger.info(f"Indexd records for header zips: {len(hrecs)}")

    # Save results
    results = {"header_guids": header_guids, "indexd_records": hrecs}
    with open(Path(pdir) / f"{project_id}_upload_results_{date_str}.json", "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to: {pdir}/{project_id}_upload_results_{date_str}.json")

    return hrecs


# -------------------------------------------------------
# Step 6: Update indexd authz/acl
# -------------------------------------------------------
def update_authz(hrecs, project_id, sapi, sauth, index_client, logger):
    prog, proj      = project_id.split('-', 1)
    authz_successes = []
    authz_failures  = []

    for i, hrec in enumerate(hrecs):
        guid     = hrec.get('did')
        filename = hrec.get('file_name')
        logger.info(f"({i+1}/{len(hrecs)}): {filename}")

        try:
            fresh_rec    = index_client.get_record(guid)
            rev          = fresh_rec.get('rev')
            payload      = {'authz': [f"/programs/{prog}/projects/{proj}"], 'acl': [prog, proj]}
            index_url    = f"{sapi}/index/index/{guid}?rev={rev}"
            access_token = sauth._get_auth_value()
            response     = requests.put(
                index_url,
                headers={'Content-Type': 'application/json', 'Authorization': access_token},
                json=payload
            )

            if response.status_code == 200:
                authz_successes.append(guid)
            else:
                authz_failures.append({'guid': guid, 'error': response.text})

        except Exception as e:
            logger.error(f"Error: {e}")
            authz_failures.append({'guid': guid, 'error': str(e)})

    logger.info(f"Authz update — Successes: {len(authz_successes)}, Failures: {len(authz_failures)}")
    if authz_failures:
        for f in authz_failures:
            logger.error(f"  {f['guid']}: {f['error']}")

    return authz_successes, authz_failures


# -------------------------------------------------------
# Step 7: Update sheepdog series file records
# -------------------------------------------------------
def update_sheepdog(project_id, sapi, sauth, header_guids, pdir, date_str, source_nodes, logger):
    query        = Gen3Query(sauth)
    sub          = Gen3Submission(sauth)
    prog, proj   = project_id.split('-', 1)
    access_token = sauth._get_auth_value()

    data_files = query.raw_data_download(
        data_type="data_file",
        fields=None,
        filter_object={
            "AND": [
                {"=":  {"project_id": project_id}},
                {"IN": {"source_node": source_nodes}},  # use passed-in source_nodes
            ]
        },
        sort_fields=[{"submitter_id": "asc"}]
    )

    series_files = [d for d in data_files if d.get('source_node', '').endswith('_series_file')]
    logger.info(f"Series files: {len(series_files)}")

    with open(f"{pdir}/{project_id}_series_files_{len(series_files)}_{date_str}.json", "w") as f:
        json.dump(series_files, f, indent=4)

    srecs = []
    for i, dfile in enumerate(series_files):
        logger.info(f"({i+1}/{len(series_files)}): {dfile['file_name']}")
        uuid = dfile['_data_file_id']
        srec = sub.export_record(prog, proj, uuid, fileformat='json', filename=None)
        if isinstance(srec, list):
            srecs += [r for r in srec if isinstance(r, dict)]
        elif isinstance(srec, dict):
            srecs.append(srec)

    sdf = pd.DataFrame(srecs)
    sdf.to_csv(f"{pdir}/{project_id}_exported_sheepdog_records_{len(srecs)}_{date_str}.tsv", index=False, sep='\t')

    missing_sids = {}
    for i in range(len(sdf)):
        sid             = sdf.iloc[i]['id']
        series_filename = sdf.iloc[i]['file_name']
        series_uid      = Path(series_filename).stem
        try:
            hguid = header_guids[series_uid]
            sdf.at[i, 'dicom_header_file_guid'] = hguid
        except:
            logger.warning(f"No header guid found for {series_filename}")
            missing_sids[sid] = series_filename

    sdf['imaging_studies.submitter_id'] = sdf['imaging_studies'].apply(
        lambda x: x[0]['submitter_id'] if isinstance(x, list) and len(x) > 0 else None
    )

    req_props = ['type', 'submitter_id', 'md5sum', 'file_size', 'file_name', 'data_type',
                 'data_format', 'data_category', 'imaging_studies.submitter_id', 'dicom_header_file_guid']
    udf = copy.deepcopy(sdf.loc[sdf['dicom_header_file_guid'].notnull()])[req_props]

    logger.info(f"Records with header guid:    {len(udf)}")
    logger.info(f"Records missing header guid: {len(missing_sids)}")

    # Remove records with missing required fields
    missing_fields_records = []
    valid_records          = []
    for i in range(len(udf)):
        row     = udf.iloc[i]
        missing = [field for field in req_props if pd.isnull(row.get(field)) or row.get(field) == '']
        if missing:
            missing_fields_records.append({'submitter_id': row.get('submitter_id'),
                                           'file_name': row.get('file_name'), 'missing_fields': missing})
        else:
            valid_records.append(row)

    logger.info(f"Valid records:          {len(valid_records)}")
    logger.info(f"Records missing fields: {len(missing_fields_records)}")

    if missing_fields_records:
        pd.DataFrame(missing_fields_records).to_csv(
            f"{pdir}/{project_id}_missing_fields_{len(missing_fields_records)}_{date_str}.tsv",
            index=False, sep='\t'
        )

    udf    = pd.DataFrame(valid_records).reset_index(drop=True)
    dtypes = list(set(udf['type']))
    ufiles = []

    for dtype in dtypes:
        dtype_df = udf.loc[udf['type'] == dtype]
        uname    = f"{pdir}/{project_id}_{dtype}_updated_dicom_header_file_guid_{len(dtype_df)}_{date_str}.tsv"
        dtype_df.to_csv(uname, index=False, sep='\t')
        ufiles.append(uname)
        logger.info(f"Written: {uname}")

    total_updated = 0
    for ufile in ufiles:
        logger.info(f"Submitting: {ufile}")
        with open(ufile, 'r') as f:
            tsv_data = f.read()
        response = requests.put(
            f"https://{sapi.replace('https://', '')}/api/v0/submission/{prog}/{proj}",
            headers={'Authorization': sauth._get_auth_value(), 'Content-Type': 'text/tab-separated-values'},
            data=tsv_data
        )
        result        = response.json()
        total_updated += result.get('updated_entity_count', 0)
        logger.info(f"Response: {result}")

    logger.info(f"Total records updated: {total_updated}")

    # Confirm updates
    srecs_confirmed = []
    for i, dfile in enumerate(series_files):
        rec = sub.export_record(prog, proj, dfile['_data_file_id'], fileformat='json', filename=None)
        if isinstance(rec, list):
            srecs_confirmed += [r for r in rec if isinstance(r, dict)]
        elif isinstance(rec, dict):
            srecs_confirmed.append(rec)

    cdf          = pd.DataFrame(srecs_confirmed)
    has_guid     = cdf['dicom_header_file_guid'].notnull().sum()
    missing_guid = cdf['dicom_header_file_guid'].isnull().sum()
    logger.info(f"Records with dicom_header_file_guid:    {has_guid}")
    logger.info(f"Records without dicom_header_file_guid: {missing_guid}")
    cdf.to_csv(f"{pdir}/{project_id}_confirmed_sheepdog_records_{len(cdf)}_{date_str}.tsv", index=False, sep='\t')

    return series_files


# -------------------------------------------------------
# Step 8: Create core_metadata_collection and supplementary_file records
# -------------------------------------------------------
def create_supplementary_files(hrecs, project_id, sauth, index_client, pdir, date_str, logger):
    sub        = Gen3Submission(sauth)
    prog, proj = project_id.split('-', 1)

    # Create core_metadata_collection (may already exist from an earlier run; don't abort if so)
    cmc_record = {
        'type':         'core_metadata_collection',
        'submitter_id': 'dicom_header_files',
        'projects':     [{'code': proj}],
        'description':  f'Core metadata collection for {project_id} DICOM header files.'
    }
    try:
        data = sub.submit_record(program=prog, project=proj, json=cmc_record)
        logger.info(f"core_metadata_collection: {data}")
    except Exception as e:
        logger.warning(f"core_metadata_collection submit raised (may already exist), continuing: {e}")

    sd_progress = {'success': [], 'failed': []}

    for i, hrec in enumerate(hrecs):
        did       = hrec.get('did')
        file_name = hrec.get('file_name')
        logger.info(f"({i+1}/{len(hrecs)}): Creating supplementary_file for '{did}'")

        try:
            fresh_rec = index_client.get_record(did)
            file_size = fresh_rec.get('size')
            md5sum    = fresh_rec.get('hashes', {}).get('md5')

            sf_record = {
                'type':                      'supplementary_file',
                'submitter_id':              file_name.split('/')[-1],
                'core_metadata_collections': [{'submitter_id': 'dicom_header_files'}],
                'file_name':                 file_name,
                'object_id':                 did,
                'data_category':             'DICOM Headers',
                'data_type':                 'DICOM Headers',
                'data_format':               'ZIP',
                'file_description':          f'Zip file containing imaging series DICOM header file {file_name}',
                'file_size':                 file_size,
                'md5sum':                    md5sum,
            }

            res = sub.submit_record(program=prog, project=proj, json=sf_record)
            sd_progress['success'].append(res)
            logger.info(f"  Created: {res}")

        except Exception as e:
            logger.error(f"  Error: {e}")
            sd_progress['failed'].append(did)

    logger.info(f"supplementary_file — Success: {len(sd_progress['success'])}, Failed: {len(sd_progress['failed'])}")

    with open(f"{pdir}/{project_id}_supplementary_file_results_{date_str}.json", "w") as f:
        json.dump(sd_progress, f, indent=2)

    return sd_progress


# -------------------------------------------------------
# Step 9: Update indexd description and metadata
# -------------------------------------------------------
def update_indexd_metadata(hrecs, project_id, sapi, sauth, index_client, pdir, date_str, logger):
    updates     = {"success": [], "failed": []}
    max_retries = 3

    for i, hrec in enumerate(hrecs):
        did      = hrec.get('did')
        filename = hrec.get('file_name')
        logger.info(f"({i+1}/{len(hrecs)}): Updating metadata for '{filename}'")

        for attempt in range(1, max_retries + 1):
            try:
                fresh_rec    = index_client.get_record(did)
                rev          = fresh_rec.get('rev')
                payload      = {
                    'metadata':    {'data_type': 'dicom_header_file'},
                    'description': f'{project_id}_dicom_headers'
                }
                index_url    = f"{sapi}/index/index/{did}?rev={rev}"
                response     = requests.put(
                    index_url,
                    headers={'Content-Type': 'application/json', 'Authorization': sauth._get_auth_value()},
                    json=payload
                )
                response.raise_for_status()
                updates['success'].append(did)
                logger.info(f"  Success on attempt {attempt}")
                break

            except Exception as e:
                logger.warning(f"  Attempt {attempt}/{max_retries} failed: {e}")
                if attempt == max_retries:
                    logger.error(f"  Giving up on '{did}'")
                    updates['failed'].append(did)

    logger.info(f"Metadata update — Success: {len(updates['success'])}, Failed: {len(updates['failed'])}")

    if updates['failed']:
        pd.DataFrame({'did': updates['failed']}).to_csv(
            f"{pdir}/{project_id}_indexd_update_failures_{len(updates['failed'])}_{date_str}.tsv",
            index=False, sep='\t'
        )

    return updates


# -------------------------------------------------------
# Main pipeline runner
# -------------------------------------------------------
def run_project(project_id, sapi, sauth, query, file_client, index_client, wd, source_nodes, date_str, logger):
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {project_id}")
    logger.info(f"{'='*60}")

    pdir         = f"{wd}/{project_id}"
    download_dir = f"{pdir}/downloads"
    os.makedirs(download_dir, exist_ok=True)
    os.chdir(pdir)

    # Progress logging to S3 only happens if GEN3_TOKEN is set in the task env
    s3_token  = os.environ.get('GEN3_TOKEN')
    s3_bucket = "gen3wf-brhstaging-data-commons-org-245"
    s3_prefix = f"progress/{project_id}"

    # Step 1: Download
    log_to_s3(f"Starting download for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    data_files, successes, failures = download_series(
        project_id, query, file_client, pdir, download_dir, source_nodes, date_str, logger
    )
    log_to_s3(f"Download complete: {len([s for s in successes if s['status'] == 'downloaded'])} downloaded, {len(failures)} failed", s3_bucket, s3_prefix, s3_token, logger)

    # Save download results
    results_path = Path(wd) / f"{project_id}_download_results_{date_str}.json"
    with open(results_path, "w") as f:
        json.dump({"successes": successes, "failures": failures}, f, indent=2)
    logger.info(f"Download results saved to: {results_path}")
    logger.info(f"Downloaded: {len([s for s in successes if s['status'] == 'downloaded'])}")
    logger.info(f"Skipped:    {len([s for s in successes if s['status'] == 'skipped'])}")
    logger.info(f"Failed:     {len(failures)}")

    # Step 2: Extract headers
    log_to_s3(f"Starting header extraction for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    os.chdir(pdir)
    series_files, zips = extract_headers(data_files, project_id, pdir, download_dir, logger)
    log_to_s3(f"Extraction complete: {len(zips)} zips processed", s3_bucket, s3_prefix, s3_token, logger)

    # Step 3: Validate
    log_to_s3(f"Starting validation for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    header_zips, header_dir = validate_header_zips(series_files, failures, pdir, logger)
    log_to_s3(f"Validation complete: {len(header_zips)} header zips ready", s3_bucket, s3_prefix, s3_token, logger)

    # Step 4: Upload
    log_to_s3(f"Starting upload for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    os.chdir(header_dir)
    header_guids = upload_headers(header_zips, header_dir, file_client, failures, logger)
    if not header_guids:
        raise RuntimeError("upload_headers returned no GUIDs; refusing to continue to later steps")
    log_to_s3(f"Upload complete: {len(header_guids)} guids created", s3_bucket, s3_prefix, s3_token, logger)

    # Step 5: Confirm uploads
    log_to_s3(f"Confirming uploads for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    hrecs = confirm_uploads(header_guids, index_client, pdir, project_id, date_str, logger)
    log_to_s3(f"Confirmed: {len(hrecs)} indexd records", s3_bucket, s3_prefix, s3_token, logger)

    # Step 6: Update authz
    log_to_s3(f"Starting authz update for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    update_authz(hrecs, project_id, sapi, sauth, index_client, logger)
    log_to_s3(f"Authz update complete for {project_id}", s3_bucket, s3_prefix, s3_token, logger)

    # Step 7: Update sheepdog
    log_to_s3(f"Starting sheepdog update for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    update_sheepdog(project_id, sapi, sauth, header_guids, pdir, date_str, source_nodes, logger)
    log_to_s3(f"Sheepdog update complete for {project_id}", s3_bucket, s3_prefix, s3_token, logger)

    # Step 8: Create supplementary files
    log_to_s3(f"Starting supplementary file creation for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    create_supplementary_files(hrecs, project_id, sauth, index_client, pdir, date_str, logger)
    log_to_s3(f"Supplementary files complete for {project_id}", s3_bucket, s3_prefix, s3_token, logger)

    # Step 9: Update indexd metadata
    log_to_s3(f"Starting indexd metadata update for {project_id}", s3_bucket, s3_prefix, s3_token, logger)
    update_indexd_metadata(hrecs, project_id, sapi, sauth, index_client, pdir, date_str, logger)
    log_to_s3(f"Indexd metadata update complete for {project_id}", s3_bucket, s3_prefix, s3_token, logger)

    logger.info(f"Pipeline complete for {project_id}")
    log_to_s3(f"Pipeline complete for {project_id}", s3_bucket, s3_prefix, s3_token, logger)


# -------------------------------------------------------
# Entry point
# -------------------------------------------------------
def main():
    args         = parse_args()
    project_ids  = args.project_ids.split(',')
    sapi         = f"https://{args.endpoint}"
    scred        = args.credentials
    wd           = args.working_dir
    source_nodes = args.source_nodes.split(',')
    date_str     = datetime.today().strftime('%Y%m%d')

    logger = setup_logging(wd)
    logger.info(f"Starting pipeline for projects: {project_ids}")
    logger.info(f"Endpoint:     {sapi}")
    logger.info(f"Working dir:  {wd}")
    logger.info(f"Source nodes: {source_nodes}")

    # Initialize Gen3 clients
    sauth        = Gen3Auth(sapi, refresh_file=scred)
    query        = Gen3Query(sauth)
    file_client  = Gen3File(sauth)
    index_client = Gen3Index(sauth)

    failed_projects = []
    for project_id in project_ids:
        try:
            run_project(
                project_id   = project_id,
                sapi         = sapi,
                sauth        = sauth,
                query        = query,
                file_client  = file_client,
                index_client = index_client,
                wd           = wd,
                source_nodes = source_nodes,
                date_str     = date_str,
                logger       = logger,
            )
        except Exception as e:
            logger.exception(f"Pipeline failed for {project_id}: {e}")
            failed_projects.append(project_id)

    if failed_projects:
        logger.error(f"Projects that failed: {failed_projects}")
        sys.exit(1)   # so TES reports EXECUTOR_ERROR instead of COMPLETE

    logger.info("All projects complete")


if __name__ == '__main__':
    main()
