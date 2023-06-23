#!/usr/bin/env python3

import os
import argparse
import numpy as np
import evaluate
import wandb
import torch
from itertools import chain, repeat
from transformers import DataCollatorForLanguageModeling
from psutil import virtual_memory
from datasets import load_dataset
from transformers import GPT2Tokenizer, GPT2Model, GPT2LMHeadModel, AutoTokenizer
from transformers import TrainingArguments, Trainer


def test_model(tokenizer, prompt, max_length, model_dir):
    # load fine-tuned model from local directory where model is saved
    ft_model = GPT2LMHeadModel.from_pretrained(model_dir)
    # test prompt completion
    # input_sequence = "peptidyl-prolyl isomerase"
    # input_sequence = "ADGRV1 gene synonyms are "
    # input_sequence = "alcohol history is"
    # input_sequence = "Tell me about Genomic DNA change chr5:g.90778903C>T"
    # input_sequence = "ENST00000405460 is a "
    enc = tokenizer(prompt, return_tensors="pt")
    print("enc:", enc)
    input_ids = enc["input_ids"]
    attention_mask = enc["attention_mask"]
    print("generating greedy output")
    # greedy output
    greedy = ft_model.generate(
        input_ids,
        max_length=max_length,
        generation_config=ft_model.generation_config,
        output_scores=True,
        return_dict_in_generate=True,
    )
    # inspect loss
    # outs = model(input_ids= input_ids)
    # print(outs)
    print("generating beam search outputs")
    beam = ft_model.generate(
        input_ids,
        max_length=max_length,
        num_beams=5,
        no_repeat_ngram_size=2,
        num_return_sequences=5,
        early_stopping=True,
        output_scores=True,
        return_dict_in_generate=True,
    )
    print("top_k0 sampling")
    top_k0 = ft_model.generate(
        input_ids,
        do_sample=True,
        max_length=max_length,
        top_k=0,
        temperature=0.2,
        output_scores=True,
        return_dict_in_generate=True,
    )
    print("top_k50 sampling")
    top_k50 = ft_model.generate(
        input_ids,
        do_sample=True,
        max_length=max_length,
        top_k=50,
        output_scores=True,
        return_dict_in_generate=True,
    )
    print("top_p nucleus sampling")
    top_p = ft_model.generate(
        input_ids,
        do_sample=True,
        max_length=max_length,
        top_p=0.1,
        top_k=0,
        output_scores=True,
        return_dict_in_generate=True,
    )
    print("top_p and top_k sampling")
    top_p_top_k50 = ft_model.generate(
        input_ids,
        do_sample=True,
        max_length=max_length,
        top_p=0.1,
        top_k=50,
        output_scores=True,
        return_dict_in_generate=True,
    )
    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "greedy": greedy,
        "beam": beam,
        "top_k0": top_k0,
        "top_k50": top_k50,
        "top_p": top_p,
        "top_p_top_k50": top_p_top_k50,
    }


def load_tokenizer():
    # load GPT2 tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained(
        "gpt2-large", force_download=True, resume_download=False
    )
    # the pad token seems correct for GPT2, see https://github.com/huggingface/transformers/issues/12594
    tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prompt", dest="prompt", required=True
    )  # using pytorch 2.0 nightly
    parser.add_argument("--max-length", dest="max_length", required=True)
    parser.add_argument("--model-dir", dest="model_dir", required=True)
    args = parser.parse_args()
    return args


def parse_results(results, model_dir, tokenizer):
    print("parsing results for {}".format(model_dir))
    print("copy input_ids and attn_mask to cuda")
    input_ids = results["input_ids"].to("cuda")
    attention_mask = results["attention_mask"].to("cuda")
    for k, v in results.items():
        if k != "input_ids" and k != "attention_mask":
            if k == "top_p_top_k50" or k == "beam":
                print("#### result from {} sampling".format(k))
                for i, sample_output in enumerate(results[k]):
                    print(
                        "{}:{}".format(
                            i, tokenizer.decode(sample_output, skip_special_tokens=True)
                        )
                    )
            else:
                print("#### result from {} sampling".format(k))
                print(tokenizer.decode(results[k][0], skip_special_tokens=True))
                print("#### getting probability dist of tokens")

                # get softmax dot product probs on the logits
                # output.scores has a shape of (batch_size x sequence_length x vocabulary_size)
                probs = torch.nn.functional.softmax(results[k].scores, dim=-1)
                print("softmax probs {}".format(probs))
                decoded_tokens = tokenizer.convert_ids_to_tokens(results[k].sequences)
                print("decoded tokens {}".format(decoded_tokens))
                # get list of token prob pairs

                token_prob_pairs = list(zip(decoded_tokens, token_probs))
                # print the token prob pairs
                for token, prob in token_prob_pairs:
                    print(f"Token: {token}, Probability: {prob}")

    return


def main(argv=None):
    args = parse_args()
    prompt = args.prompt
    max_length = int(args.max_length)
    model_dir = args.model_dir
    tokenizer = load_tokenizer()
    print("********* test fine tuned model ********")
    ft_results = test_model(tokenizer, prompt, max_length, model_dir)

    parse_results(results=ft_results, model_dir=model_dir, tokenizer=tokenizer)

    print("********* test baseline model ********")
    baseline_model = "gpt2-large"
    baseline_results = test_model(
        tokenizer, prompt, max_length, model_dir=baseline_model
    )
    parse_results(
        results=baseline_results, model_dir=baseline_model, tokenizer=tokenizer
    )


if __name__ == "__main__":
    main()
