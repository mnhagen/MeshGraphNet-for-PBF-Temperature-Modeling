# model_training

model_training is the folder in which the MeshGraphNet is defined and trained using the parameters in the config file. While the training can be done locally in theory, it is highly recommended to use one of the GPU clusters. There are three clusters available at NLR titled uxcs02, uxcs03 and uxcs04. Uxcs02 is too old, the installed GPU drivers are not supported by the required python packages. uxcs04 is the newest cluster with the best GPUs and the most memory, but I did gain access to it until after I finished training my models. I therefore used uxcs03 for model training, and this step by step guide therefore shows how to connect to and train on uxcs03. I do recommend, however, looking into how to gain access to and train the models on uxcs04.

# How to use

To train the model, you must first place the relevant files in the shared folder. The shared folder has a path like '\\smb-nop01\shared'; it should be easy to find in the file explorer. Copy this folder (model_training) and the datasets folder into the shared folder. You only need to copy over the dataset you need for training, but make sure it is still in the correct folder structure (datasets\dataset_name). You also need to set up a virtual environment on the cluster.


To train the model, follow these steps:

- Open cmd and connect to the cluster using the following command:

```text
ssh username@uxcs03
```

- Enter your password when prompted.

- Activate your virtual environment.

- Start training the model using the following command:

```text
python -m model_training.meshgraphnet
```

- When the model is finished training, copy the model folder back to your local machine. The trained model can be found in the models folder in the shared directory.

The progress of the training will be printed after each epoch. To monitor resource usage, 'top' and 'nvidia-smi' can be used in a separate cmd also logged in to uxcs03. 'watch -n 1 nvidia-smi' gives a live view of GPU usage that updates every second.

# training_config

Here is an overview of the parameters in training_config.json and what they do:

- `dataset_path`: relative path to the dataset folder. To keep with the structure of the project, just change the last part to whatever you want to name the dataset.
- `root_path`: absolute path to the folder where the datasets and model_training folders are kept. If training on a cluster, this will be the shared folder. Update the root path before using as the current directory leads to my shared folder, which will not work for you.
- `model_name`: name of the model to be trained. This will be the name of the folder in which the model will be saved.
- `latent_width`: size of the latent space in the MeshGraphNet.
- `num_processor_blocks`: number of processor blocks stacked in the MeshGraphNet. Read my report for more details.
- `batch_size`: number of graphs to be processed in one batch. Setting this to greater than 1 was found to consume too much memory.
- `max_epochs`: maximum number of epochs to train for.
- `patience`: number of epochs to wait for improvement in validation loss before early stopping.
- `learning_rate`: learning rate for the optimizer.
- `use_layer_norm`: whether to use layer normalization in the MeshGraphNet.
- `try_device`: device to try to train on. If set to "cuda", the code will try to use the GPU. If "cuda" is not available, it will fall back to CPU. The device used is printed to the console for confirmation.
- `min_rel_delta`: minimum relative change in validation loss required to consider it an improvement.
- `accumulation_steps`: number of steps to accumulate gradients before updating the model parameters. This was included to approximate the effect of using a larger batch size, but was not found to lead to lower losses during testing and is thus kept at 1 now.