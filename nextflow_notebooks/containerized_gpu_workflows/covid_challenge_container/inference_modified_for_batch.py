import os, shutil, pdb, math, random
import argparse
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import torch.backends.cudnn as cudnn
import torch
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Dataset
import pydicom
from skimage import exposure, transform
from PIL import Image
from scipy.stats import norm
from torchvision.models import efficientnet_v2_m, swin_b
import torch.nn as nn
import glob
import sys


class CV19DataSet(Dataset):
    def __init__(self, df, transform, img_size=224):
        self.filenames = df.fileNamePath.tolist()
        self.transform = transform
        self.img_size = img_size

    def __getitem__(self, index):
        fn = self.filenames[index]
        info = pydicom.dcmread(fn, stop_before_pixels=False)
        dicom_img = info.pixel_array.astype(np.float32)
        output_size = 1024
        img = transform.resize(
            dicom_img,
            (output_size, output_size),
            order=1,
            preserve_range=True,
            anti_aliasing=True,
        )

        if hasattr(info, "WindowCenter") & hasattr(info, "WindowWidth"):
            window_level = info.WindowCenter
            window_width = info.WindowWidth
            if type(window_level) == pydicom.multival.MultiValue:
                window_level = window_level[0]
                window_width = window_width[0]
        else:
            window_width = np.max(dicom_img) - np.min(dicom_img)
            window_level = np.min(dicom_img) + 0.5 * window_width
        img = exposure.rescale_intensity(
            img,
            in_range=(
                window_level - window_width * 0.5,
                window_level + window_width * 0.5,
            ),
            out_range=(0.0, 1.0),
        )
        img = np.uint8(img * 255)

        if hasattr(info, "PhotometricInterpretation"):
            PhotometricInterpretation = str(info.PhotometricInterpretation)
            if PhotometricInterpretation.lower() == "MONOCHROME1".lower():
                img = 255 - img

        img = Image.fromarray(img).convert("RGB")
        img = img.resize((self.img_size, self.img_size), resample=Image.BILINEAR)

        if self.transform is not None:
            img = self.transform(img)
        return img

    def __len__(self):
        return len(self.filenames)


def model_test(model, dataLoader, device):
    model.eval()
    pred = torch.FloatTensor()
    pred = pred.to(device)
    with torch.no_grad():
        for i, inp in enumerate(dataLoader):
            output = model(inp.to(device))
            pred = torch.cat((pred, output.data), 0)
    pred_np = pred.cpu().detach().numpy()
    del pred
    return pred_np[:, 0]


def get_covid_score(df, device="cpu"):
    model_list = glob.glob("/app/*.pth.tar")
    print("model_list {}".format(model_list))
    num_models = len(model_list)
    N_CLASSES = 2
    normalizer = [[0.485, 0.456, 0.406], [0.229, 0.224, 0.225]]
    transformSequence_test = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize(normalizer[0], normalizer[1])]
    )

    test_dataset_224 = CV19DataSet(
        df=df, transform=transformSequence_test, img_size=224
    )
    test_loader_224 = DataLoader(
        dataset=test_dataset_224,
        batch_size=64,
        shuffle=False,
        num_workers=0,
        pin_memory=False,
        drop_last=False,
        persistent_workers=False,
    )

    test_dataset_480 = CV19DataSet(
        df=df, transform=transformSequence_test, img_size=480
    )
    test_loader_480 = DataLoader(
        dataset=test_dataset_480,
        batch_size=16,
        shuffle=False,
        num_workers=0,
        pin_memory=False,
        drop_last=False,
        persistent_workers=False,
    )

    pred_np_total = np.zeros((len(df), num_models))
    for model_index in range(num_models):
        model_name = model_list[model_index]
        print("model path:", model_name)
        # initialize and load the model

        if "Swin" in model_name:
            model = swin_b(weights=None)
            model.head = nn.Sequential(nn.Linear(1024, N_CLASSES), nn.Softmax(dim=1))
            model = nn.DataParallel(model).cuda()

            if os.path.isfile(model_name):
                checkpoint = torch.load(model_name)
                state_dict = checkpoint["state_dict"]
                model.load_state_dict(state_dict)
                pred_np = model_test(model, test_loader_224, device)
            else:
                sys.exit("no checkpoint found")

        elif "EfficientNet" in model_name:
            model = efficientnet_v2_m(weights=None)
            model.classifier[1] = nn.Sequential(
                nn.Linear(1280, N_CLASSES), nn.Softmax(dim=1)
            )
            model = nn.DataParallel(model).cuda()
            if os.path.isfile(model_name):
                checkpoint = torch.load(model_name)
                state_dict = checkpoint["state_dict"]
                model.load_state_dict(state_dict)
                pred_np = model_test(model, test_loader_480, device)
            else:
                sys.exit("no checkpoint found")
        else:
            sys.exit("no model found")
        pred_np_total[:, model_index] = pred_np

    pred_np_ensemble = np.mean(pred_np_total, axis=1)
    return pred_np_ensemble


def setup_args():
    parser = argparse.ArgumentParser()
    # example dicom_input=['/mnt/in/1-008.dcm', '/mnt/in/1-034.dcm']
    parser.add_argument(
        "--dicom-input",
        dest="dicom_input",
        nargs="+",
        help="input directory with all dicom files",
        required=True,
    )
    # example classification_out_csv = '/mnt/out/classification_results.csv'
    parser.add_argument(
        "--classification-out-csv",
        dest="classification_out_csv",
        help="output file with classification results",
        required=True,
    )
    return parser.parse_args()


def main(argv=None):
    args = setup_args()
    print("args: {}".format(args))
    dicom_input = args.dicom_input
    print("dicom_input: {}".format(dicom_input))
    classification_out_csv = args.classification_out_csv
    print("classification_out_csv: {}".format(classification_out_csv))
    # dicom_input is the directory with all dcm files
    if torch.cuda.is_available():
        device = torch.device("cuda:0")  # GPU
        cudnn.benchmark = True
    else:
        device = torch.device("cpu")  # CPU
    print(f"\n\n\n\nCUDA AVAILABLE: {torch.cuda.is_available()}\n\n\n\n")

    torch.cuda.reset_peak_memory_stats()

    # list of dicom files in dicom directory
    images = dicom_input
    print("images {}:".format(images))
    # generate dataframe
    df = pd.DataFrame({"fileNamePath": images})

    score = get_covid_score(df, device=device)
    print("score: {}".format(score))
    print("used memory", torch.cuda.max_memory_allocated() / 1073741824)

    classification_output = pd.DataFrame({"fileNamePath": images, "class": score})
    # output file
    classification_output.to_csv(classification_out_csv, index=False)


if __name__ == "__main__":
    main()


# pdb.set_trace()
