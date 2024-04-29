FROM public.ecr.aws/u5x5h6w3/nextflow-approved/public:gen3-cuda-11.8-ubuntu22.04-openssl 

# symlink python to python3
RUN ln -s /usr/bin/python3 /usr/bin/python
 
# set workdir /app
WORKDIR /app/
 
# Install requirements
COPY ./requirements.txt  /app/
RUN pip install -r requirements.txt

# Copy check_torch_cuda code to container
COPY ./check_torch_cuda.py /app/
 
CMD ["python", "check_torch_cuda.py"]
