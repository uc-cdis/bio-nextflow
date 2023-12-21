import pydicom
import argparse
import numpy as np
from PIL import Image
import os

dicom_input = "$dicom_files"


def main(dicom_input):
    png_out = dicom_input.split(".dcm")[0] + ".png"
    dicom_dataset = pydicom.dcmread(dicom_input)
    transformed_image = dicom_dataset.pixel_array.astype(float)
    scaled_image = np.uint8(
        (np.maximum(transformed_image, 0) / transformed_image.max()) * 255.0
    )
    final_image = Image.fromarray(scaled_image)
    final_image.save(png_out)


if __name__ == "__main__":
    main(dicom_input)
