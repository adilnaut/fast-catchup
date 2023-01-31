import json
import sys
import os
import importlib




from app import models

def get_dict_from_file(filepath):
    with open(filepath, 'r') as f:
        d = json.load(f)
        return d

def test_model(modelname, filename):

    if len(sys.argv) <= 1:
        exit("Call this script with model name to test!")
    # Model = models.__import__(sys.argv[1])
    Model = getattr(models, sys.argv[1])
    # Model = importlib.import_module("from app.models import %s" % sys.argv[1])

    # d = dict(p1=1, p2=2)
    # def f2(p1, p2):
    #   print(p1, p2)
    # f2(**d)
    print(Model)
    d = get_dict_from_file(sys.argv[2])
    d = dict(d)
    m = Model(**d)
    print("Model instance: %s" % m)

if __name__ == '__main__':

    if len(sys.argv) <= 1:
        exit("Call this script with model name to test!")
    # Model = models.__import__(sys.argv[1])
    Model = getattr(models, sys.argv[1])
    # Model = importlib.import_module("from app.models import %s" % sys.argv[1])

    # d = dict(p1=1, p2=2)
    # def f2(p1, p2):
    #   print(p1, p2)
    # f2(**d)
    print(Model)
    d = get_dict_from_file(sys.argv[2])
    d = dict(d)
    m = Model(**d)
    print("Model instance: %s" % m)
