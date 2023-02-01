import json
import sys
import os
import importlib


from app import models

def get_dict_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        d = json.load(f)
        return d

def return_test_instance(filepath, model_name):
    Model = getattr(models, model_name)

    filepath = os.path.join('samples', filepath)
    d = get_dict_from_file(filepath)
    d = dict(d)
    m = Model(**d)
    return m


if __name__ == '__main__':

    if len(sys.argv) <= 1:
        exit("Call this script with model name to test!")
    Model = getattr(models, sys.argv[1])


    print(Model)
    samples_folder = sys.argv[2]
    dir_list = os.listdir(samples_folder)
    for filename in dir_list:
        filepath = os.path.join(samples_folder, filename)
        d = get_dict_from_file(filepath)
        d = dict(d)
        m = Model(**d)
        print("Filename %s - Model instance: %s" % (filename, m))
