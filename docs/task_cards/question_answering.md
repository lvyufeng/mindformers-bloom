# Question Answering

## 任务描述

**问答任务**：模型在基于问答数据集的微调后，输入为上下文（context）和问题（question），模型根据上下文（context）给出相应的回答。

**相关论文**

- Jacob Devlin, Ming-Wei Chang, et al., [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding](https://arxiv.org/pdf/1810.04805.pdf), 2019.
- Pranav Rajpurkar, Jian Zhang, Konstantin Lopyrev, Percy Liang, [SQuAD: 100,000+ Questions for Machine Comprehension of Text](https://arxiv.org/pdf/1606.05250.pdf), 2016.

## 已支持数据集性能

| model |            type            |  datasets  |  EM   | F1    |           stage            |                           example                            |
| :---: | :------------------------: | :--------: | :---: | ----- | :------------------------: | :----------------------------------------------------------: |
|  q'a  | qa_bert_case_uncased_squad | SQuAD v1.1 | 80.74 | 88.33 | train<br/>eval<br/>predict | [link](../../examples/question_answering/qa_bert_base_uncased_train_on_squad.sh) <br/> [link](../../examples/question_answering/qa_bert_base_uncased_eval_on_squad.sh) <br/> [link](../../examples/question_answering/qa_bert_base_uncased_predict_on_squad.sh) |

### [SQuAD v1.1](https://rajpurkar.github.io/SQuAD-explorer/)

- 下载地址：[SQuAD v1.1训练集](https://rajpurkar.github.io/SQuAD-explorer/dataset/train-v1.1.json)，[SQuAD v1.1验证集](https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json)
- 数据集：该数据集包含 10 万个（问题，原文，答案）三元组，原文来自于 536 篇维基百科文章，而问题和答案的构建主要是通过众包的方式，让标注人员提出最多 5 个基于文章内容的问题并提供正确答案，且答案出现在原文中。
- 数据格式：json文件

 ```bash
数据集目录格式
└─squad
    ├─train-v1.1.json
    └─dev-v1.1.json
 ```

## 快速任务接口

### 脚本启动

> 需开发者提前clone工程。

- 请参考[使用脚本启动](https://gitee.com/mindspore/transformer/blob/master/README.md#%E6%96%B9%E5%BC%8F%E4%B8%80clone-%E5%B7%A5%E7%A8%8B%E4%BB%A3%E7%A0%81)

- 脚本运行测试

```shell
# finetune
python run_mindformer.py --config ./configs/qa/run_qa_bert_base_uncased.yaml --run_mode finetune

# evaluate
python run_mindformer.py --config ./configs/qa/run_qa_bert_base_uncased.yaml --run_mode eval --load_checkpoint qa_bert_base_uncased_squad

# predict
python run_mindformer.py --config ./configs/qa/run_qa_bert_base_uncased.yaml --run_mode predict --load_checkpoint qa_bert_base_uncased_squad --predict_data [TEXT]
```

### 调用API启动

- Trainer接口开启评估/推理：

  ```python
  import os
  from mindformers import MindFormerBook
  from mindformers.trainer import Trainer
  from mindformers import build_dataset, MindFormerConfig
  from mindformers import AutoTokenizer

  # 构造数据集
  project_path = MindFormerBook.get_project_path()
  dataset_config = MindFormerConfig(os.path.join(project_path, "configs",
                                    "qa", "task_config", "bert_squad_dataset.yaml"))

  # 将SQuAD v1.1数据集放置到路径：./squad
  dataset = build_dataset(dataset_config.eval_dataset_task)

  # 创建 tokenizer
  tokenizer = AutoTokenizer.from_pretrained('qa_bert_base_uncased_squad')

  # 显示Trainer的模型支持列表
  MindFormerBook.show_trainer_support_model_list("question_answering")
  # INFO - Trainer support model list for question_answering task is:
  # INFO -    ['qa_bert_base_uncased']
  # INFO - -------------------------------------

  # 初始化trainer
  trainer = Trainer(task='question_answering',
                    model='qa_bert_base_uncased',
                    eval_dataset=dataset)

  # 测试数据，测试数据分为context和question两部分，两者以 “-” 分隔
  input_data = ["My name is Wolfgang and I live in Berlin - Where do I live?"]

  # 微调训练
  trainer.train(resume_or_finetune_from_checkpoint="qa_bert_base_uncased",
                do_finetune=True)

  # 进行评估
  trainer.evaluate(eval_checkpoint='./output/rank_0/checkpoint/mindformers_rank_0-2_7386.ckpt')
  # INFO - QA Metric = {'QA Metric': {'exact_match': 80.74739829706716, 'f1': 88.33552874684968}}

  # 进行推理
  trainer.predict(predict_checkpoint='./output/rank_0/checkpoint/mindformers_rank_0-2_7386.ckpt',
                  input_data=input_data)
  # INFO - output result is [{'text': 'Berlin', 'score': 0.9941, 'start': 34, 'end': 40}]
  ```

- pipeline接口开启快速推理

  ```python
  from mindformers.pipeline import QuestionAnsweringPipeline
  from mindformers import AutoTokenizer, BertForQuestionAnswering, AutoConfig

  # 测试数据，测试数据分为context和question两部分，两者以 “-” 分隔
  input_data = ["My name is Wolfgang and I live in Berlin - Where do I live?"]

  tokenizer = AutoTokenizer.from_pretrained('qa_bert_base_uncased_squad')
  qa_squad_config = AutoConfig.from_pretrained('qa_bert_base_uncased_squad')

  # This is a known issue, you need to specify batch size equal to 1 when creating bert model.
  qa_squad_config.batch_size = 1

  model = BertForQuestionAnswering(qa_squad_config)
  qa_pipeline = QuestionAnsweringPipeline(task='question_answering',
                                          model=model,
                                          tokenizer=tokenizer)

  results = qa_pipeline(input_data)
  print(results)
  # 输出
  # [{'text': 'Berlin', 'score': 0.9941, 'start': 34, 'end': 40}]
  ```