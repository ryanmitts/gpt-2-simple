import glob
import numpy as np
import os
import random
import tensorflow as tf
import tqdm
import csv


def load_dataset(enc, path, combine):
    paths = []
    if os.path.isfile(path):
        # Simple file
        paths.append(path)
    elif os.path.isdir(path):
        # Directory
        for (dirpath, _, fnames) in os.walk(path):
            for fname in fnames:
                paths.append(os.path.join(dirpath, fname))
    else:
        # Assume glob
        paths = glob.glob(path)

    token_chunks = []
    tokens = []
    for path in tqdm.tqdm(paths):
        if path.endswith('.npz'):
            # Pre-encoded
            with np.load(path, allow_pickle=True) as npz:
                for item in npz.files:
                    token_chunks.append(npz[item])
        if path.endswith('.npy'):
            token_chunks.append(np.load(path, allow_pickle=True))
        elif path.endswith('.csv'):
            start_token = "<|startoftext|>"
            end_token = "<|endoftext|>"
            with open(path, 'r', encoding='utf8', errors='ignore') as fp:
                fp.readline()   # skip header
                reader = csv.reader(fp)
                for row in reader:
                    raw_text += start_token + row[0] + end_token + "\n"
        else:
            # Plain text
            with open(path, 'r', encoding='utf8', errors='ignore') as fp:
                raw_text_lines = fp.readlines()
                for raw_text in raw_text_lines:
                    tokens += enc.encode(raw_text) + [enc.encoder['<|endoftext|>']]

            if len(tokens) >= combine:
                token_chunks.append(np.stack(tokens))
                tokens = []

    if len(tokens):
        token_chunks.append(np.stack(tokens))
    return token_chunks


def binary_search(f, lo, hi):
    if f(lo) or not f(hi):
        return None
    while hi > lo + 1:
        mid = (lo + hi) // 2
        if f(mid):
            hi = mid
        else:
            lo = mid
    return hi


class Sampler(object):
    """Fairly samples a slice from a set of variable sized chunks.

    'Fairly' means that the distribution is the same as sampling from one concatenated chunk,
    but without crossing chunk boundaries."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.total_size = sum(chunk.shape[0] for chunk in chunks)
        self.boundaries = [0]
        for i in range(len(chunks)):
            self.boundaries.append(self.boundaries[-1] + chunks[i].shape[0])

    def sample(self, length):
        assert length < self.total_size // len(
            self.chunks
        ), "Dataset files are too small to sample {} tokens at a time".format(
            length)
        while True:
            index = random.randint(0, self.total_size - length - 1)
            i = binary_search(lambda j: self.boundaries[j] > index, 0,
                              len(self.boundaries) - 1) - 1
            if self.boundaries[i + 1] > index + length:
                within_chunk = index - self.boundaries[i]
                return self.chunks[i][within_chunk:within_chunk + length]
