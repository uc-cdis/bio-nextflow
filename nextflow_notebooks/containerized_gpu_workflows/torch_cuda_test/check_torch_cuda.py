import torch


def main(argv=None):
    is_torch_cuda_available = torch.cuda.is_available()
    device = torch.device("cuda:0")
    print(
        "Is torch cuda available, device {} {}".format(is_torch_cuda_available, device)
    )


if __name__ == "__main__":
    main()
