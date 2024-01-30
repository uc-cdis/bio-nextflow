FROM quay.io/cdis/containers:gen3-cuda-11.8-ubuntu22.04-openssl

# symlink python to python3
RUN ln -s /usr/bin/python3 /usr/bin/python


# Karen additions to our base image above
WORKDIR /app/

# Install requirements
COPY ./requirements.txt  /app/
RUN pip install -r requirements.txt

# Algorithm
COPY ./inference_modified_for_batch.py /app/
COPY ./EfficientNet_train_1.pth.tar  /app/
COPY ./EfficientNet_train_2.pth.tar  /app/
COPY ./EfficientNet_train_4.pth.tar  /app/
COPY ./Swin_train_0.pth.tar  /app/
COPY ./Swin_train_3.pth.tar  /app/
COPY ./Swin_train_4.pth.tar  /app/

CMD ["python", "inference_modified_for_batch.py"]
