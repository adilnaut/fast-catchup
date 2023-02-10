from transformers import AutoTokenizer, AutoModelForQuestionAnswering
from transformers import pipeline

import torch
import time
import json

def test_qa_on_bert():
    with open('context_store\morning-brew-3.txt', 'r') as f:
        context = f.read()

    print('Context characters: %s' % len(context))
    print('Context tokens: %s' % len(context.split(' ')))

    questions = []
    answers = []
    # questions.append("What should a software engineer know about this news story?")
    questions.append("Is a machine learning a sub-field of AI?")
    # questions.append("What is training data?")
    # questions.append("What is machine learning?")
    # questions.append("What is artificial intelligence?")
    # questions.append("What is generalisation?")
    # questions.append("Who introduced the concept of strong rules?")
    # questions.append("What is agriculture?")

    model_names = ['distilbert-base-cased-distilled-squad'
        , 'bert-large-uncased-whole-word-masking-finetuned-squad']

    model_paths = ['distilbert'
        , 'models\\model-1\\']

    model_index = -1

    tokenizer = AutoTokenizer.from_pretrained(model_names[model_index])
    first_time = False
    if first_time:
        model = AutoModelForQuestionAnswering.from_pretrained(model_names[model_index])
    else:
        model = AutoModelForQuestionAnswering.from_pretrained(model_paths[model_index], local_files_only=True)

    save_pretrained = False
    if save_pretrained:
        model.save_pretrained(model_path)

    for question in questions:

        start = time.time()

        inputs = tokenizer(question, context, add_special_tokens=True, return_tensors="pt", truncation=True)
        input_ids = inputs["input_ids"].tolist()[0]

        text_tokens = tokenizer.convert_ids_to_tokens(input_ids)
        model_out = model(**inputs)
        answer_start_scores = model_out.get('start_logits')
        answer_end_scores = model_out.get('end_logits')

        answer_start = torch.argmax(answer_start_scores)  # Get the most likely beginning of answer with the argmax of the score
        answer_end = torch.argmax(answer_end_scores) + 1  # Get the most likely end of answer with the argmax of the score



        answer = tokenizer.convert_tokens_to_string(tokenizer.convert_ids_to_tokens(input_ids[answer_start:answer_end]))


        end = time.time()

        answer_p = {
            'question': question,
            'answer': answer,
            'time': end - start
        }
        answers.append(answer_p)

    print(json.dumps(answers, indent=4))

def test_summary_llms():
    summarizer = pipeline("summarization")
    with open('context_store\morning-brew-agg.txt', 'r') as f:
        context = f.read()
    print(summarizer(context, max_length=200, min_length=100, do_sample=False))

if __name__ == '__main__':
    # test_qa_on_bert()
    test_summary_llms()
    pass
