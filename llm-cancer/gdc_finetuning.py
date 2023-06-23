#!/usr/bin/env python3
"""gdc_finetuning.ipynb

A very simple first test of fine tuning gpt2 on gdc data

"""

import os
import numpy as np
import evaluate
import wandb
from itertools import chain, repeat
from transformers import DataCollatorForLanguageModeling
from psutil import virtual_memory
from datasets import load_dataset
from transformers import GPT2Tokenizer, GPT2Model, GPT2LMHeadModel, AutoTokenizer
from transformers import TrainingArguments, Trainer


def import_dataset():
    # load some mini pubmed abstracts
    # input_file_name = "mini.pubmed.abstracts.txt"
    input_file_path = "/home/aartiv/huggingface/adgrv1_blurb.txt"
    # iterable_dataset = load_dataset('text', data_files={'train': input_file_path}, split="train", streaming=True)
    dataset = load_dataset(
        "text", data_files={"train": input_file_path}, split="train"
    ).train_test_split(test_size=0.2)
    return dataset


def load_tokenizer():
    # load GPT2 tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained(
        "gpt2-large", force_download=True, resume_download=False
    )
    # the pad token seems correct for GPT2, see https://github.com/huggingface/transformers/issues/12594
    tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def tokenize_function(examples):
    # padding and truncation is not supported in gpt2 tokenizer
    # we need to do these separately
    # return tokenizer(examples["text"], padding="max_length", truncation=True)
    # examples['text'] is a list of abstracts in dataset
    tokenizer = load_tokenizer()
    return tokenizer(examples["text"])


def chunk_examples(examples):
    max_seq_length = 50
    tokenizer = load_tokenizer()
    concatenated_input_ids = list(chain(*examples["input_ids"]))
    concatenated_attention_mask = list(chain(*examples["attention_mask"]))
    # split by chunks of max_seq_length
    all_chunk_input_ids = []
    all_chunk_attention_mask = []
    tot_length = len(concatenated_input_ids)
    # range(start, stop, step_size)
    for i in range(0, tot_length, max_seq_length):
        chunk_input_ids = concatenated_input_ids[i : i + max_seq_length]
        chunk_attention_mask = concatenated_attention_mask[i : i + max_seq_length]
        pad_len = max_seq_length - len(chunk_input_ids)
        # this will only be the case when max_seq_length > len(chunk_input_ids)
        # or the last item
        if pad_len != 0:
            # right padding
            chunk_input_ids.extend([tokenizer.pad_token_id] * pad_len)
            chunk_attention_mask.extend([0] * pad_len)
            # left padding -- I'm not sure if this is what we want though
            # chunk = list(repeat(tokenizer.pad_token_id, pad_len)) + chunk
        all_chunk_input_ids.append(chunk_input_ids)
        all_chunk_attention_mask.append(chunk_attention_mask)
    return {
        "input_ids": all_chunk_input_ids,
        "attention_mask": all_chunk_attention_mask,
    }


def run_ft_model_test(tokenizer):
    # load fine-tuned model from local directory where model is saved
    # ft_model = GPT2LMHeadModel.from_pretrained('test_trainer2/checkpoint-5000')
    ft_model = GPT2LMHeadModel.from_pretrained("trainer_adgrv1_v5/checkpoint-500")

    # test prompt completion
    # input_sequence = "peptidyl-prolyl isomerase"
    # input_sequence = "ADGRV1 gene synonyms are "
    # input_sequence = "alcohol history is"
    input_sequence = "Tell me about Genomic DNA change chr5:g.90778903C>T"
    # input_sequence = "ENST00000405460 is a "

    enc = tokenizer(input_sequence, return_tensors="pt")
    print("enc:", enc)
    input_ids = enc["input_ids"]
    attention_mask = enc["attention_mask"]
    greedy_output = ft_model.generate(
        input_ids, max_length=500, generation_config=ft_model.generation_config
    )
    input_ids = input_ids.to("cuda")
    attention_mask = attention_mask.to("cuda")

    # inspect loss
    # outs = model(input_ids= input_ids)
    # print(outs)
    out = tokenizer.decode(greedy_output[0])
    return out


def main(argv=None):
    ram_gb = virtual_memory().total / 1e9
    print("Your runtime has {:.1f} gigabytes of available RAM\n".format(ram_gb))
    if ram_gb < 20:
        print("Not using a high-RAM runtime")
    else:
        print("You are using a high-RAM runtime!")

    print("disable wandb")
    wandb.init(mode="disabled")
    print("loading dataset")
    dataset = import_dataset()
    print("init tokenizer")
    tokenizer = load_tokenizer()
    print("tokenizing")
    tokenized_datasets = dataset.map(tokenize_function, batched=True)
    print("chunking")
    chunked_datasets = tokenized_datasets.map(
        chunk_examples,
        batched=True,
        # remove columns 'text', to return chunked dataset with different dims
        # than small_dataset
        remove_columns=["text"],
    )
    print("begin training")
    model = GPT2LMHeadModel.from_pretrained(
        "gpt2-large"
    )  # GPT2LMHeadModel adds a language modeling head ontop of GPT2Model
    print("init training args")
    training_args = TrainingArguments(
        output_dir="trainer_adgrv1_v5",
        evaluation_strategy="epoch",
        per_device_train_batch_size=20,
        per_device_eval_batch_size=20,
        fp16=True,
        num_train_epochs=30,
        optim="adafactor",
        logging_strategy="epoch",
    )
    print("init data collator and trainer")
    data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=chunked_datasets["train"],
        eval_dataset=chunked_datasets["test"],
        data_collator=data_collator,
        tokenizer=tokenizer,
    )
    print("training")
    trainer.train()
    out = run_ft_model_test(tokenizer)
    print("output:", out)


if __name__ == "__main__":
    main()
