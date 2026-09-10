#the .ipynb is meant for running locally/inspection, this file is built for running on uxcs03

from torch_geometric.loader import DataLoader
import time
import json
from pathlib import Path

script_dir = Path(__file__).resolve().parent
config_path = script_dir / "training_config.json"

from shared.meshgraphnet_functions import *

with config_path.open("r") as f:
    training_config = json.load(f)

root_path = training_config["root_path"]
max_epochs = training_config["max_epochs"]
patience = training_config["patience"]
batch_size = training_config["batch_size"]
use_layer_norm = training_config["use_layer_norm"]
try_device = training_config["try_device"]
min_rel_delta = training_config["min_rel_delta"]
model_name = training_config["model_name"]
latent_size = training_config["latent_width"]
num_processor_blocks = training_config["num_processor_blocks"]
lr = training_config["learning_rate"]
accumulation_steps = training_config["accumulation_steps"]
dataset_path = training_config["dataset_path"]

train_path = Path(root_path, dataset_path, "train")
val_path = Path(root_path, dataset_path, "val")

unscaled_train_dataset = MeshDataset(train_path)

binary_feature_columns = [
    "is_air_boundary",
    "is_baseplate_interface",
]

continuous_feature_columns = [column for column in
    unscaled_train_dataset.feature_columns if column not in binary_feature_columns
]

feature_mean, feature_std = (
    compute_feature_statistics(
        unscaled_train_dataset,
        continuous_feature_columns,
    )
)

model_dir = Path(root_path, "models", model_name)
model_dir.mkdir(parents = True, exist_ok = True)

norm_dict = {
    "feature_mean": feature_mean.astype(float).to_dict(),
    "feature_std": feature_std.astype(float).to_dict(),
    "continuous_feature_columns": list(continuous_feature_columns)
}

with open(Path(model_dir, f"{model_name}_normalization.json"), "w") as f:
    json.dump(norm_dict, f, indent = 4)

train_dataset = MeshDataset(train_path, feature_mean, feature_std, continuous_feature_columns)
graph = train_dataset[0]

print(graph.x.shape)
print(torch.isfinite(graph.x).all())

feature_sum = torch.zeros(
    train_dataset.num_features
)

feature_squared_sum = torch.zeros(
    train_dataset.num_features
)

total_nodes = 0

for graph in train_dataset:
    feature_sum += graph.x.sum(
        dim=0
    ).cpu()

    feature_squared_sum += (
        graph.x ** 2
    ).sum(
        dim=0
    ).cpu()

    total_nodes += graph.num_nodes

mean_after_scaling = (
    feature_sum
    / total_nodes
)

variance_after_scaling = (
    feature_squared_sum
    / total_nodes
    - mean_after_scaling ** 2
)

std_after_scaling = torch.sqrt(
    variance_after_scaling.clamp(
        min=0.0
    )
)

val_dataset = MeshDataset(val_path, feature_mean, feature_std, continuous_feature_columns)

train_loader = DataLoader(train_dataset, batch_size = batch_size, shuffle = True)
val_loader = DataLoader(val_dataset, batch_size = batch_size, shuffle = False)

input_size = train_dataset.num_features

device = torch.device(try_device) if torch.cuda.is_available() else torch.device("cpu")
print(f"Using device: {device}")

if torch.cuda.is_available():
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    free_gib = free_bytes / 1024**3
    total_gib = total_bytes / 1024**3

    print(f"GPU memory free: {free_gib:.2f} GiB / {total_gib:.2f} GiB")

    if free_gib < 4:
        raise RuntimeError(
            f"Only {free_gib:.2f} GiB of GPU memory is free. "
            "Wait for the GPU to become available."
        )


checkpoint_path = model_dir / f"{model_name}.pt"



model = MeshGraphNet(node_input_size = input_size, latent_size = latent_size,
                      num_processor_blocks = num_processor_blocks)
model.to(device)
optimizer = torch.optim.Adam(model.parameters(), lr = lr, weight_decay = 1e-5)
criterion = torch.nn.MSELoss()

best_val_loss = float("inf")
epochs_without_improvement = 0

train_history = []
val_history = []
epoch_times = []

start_time = time.perf_counter()

for epoch in range(max_epochs):

    train_loss = train_one_epoch(model, train_loader, optimizer, criterion, 
                                 device, accumulation_steps)
    
    val_loss = evaluate(model, val_loader, criterion, device)

    train_history.append(train_loss)
    val_history.append(val_loss)
    if device.type == "cuda":
        torch.cuda.synchronize()

    elapsed_time = time.perf_counter() - start_time
    epoch_times.append(elapsed_time)


    improved = val_loss < best_val_loss * (1 - min_rel_delta) 

    if improved:
        best_val_loss = val_loss
        epochs_without_improvement = 0
        torch.save(
            {"epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "val_loss": val_loss
            },
            checkpoint_path
            )
        

    else:
        epochs_without_improvement += 1

    print(
        f"Epoch {epoch + 1:03d} | "
        f"train_loss: {train_loss:.6f} | "
        f"val_loss: {val_loss:.6f} | "
        f"patience: {epochs_without_improvement}/{patience}"
    )

    if epochs_without_improvement >= patience:
        print("Early stopping.")
        break

end_time = time.perf_counter()

print(f"Training time: {end_time - start_time:.2f} seconds")
print(f"Best validation loss: {best_val_loss:.6f}")

pd.DataFrame({"epoch": range(1, len(train_history) + 1),
             "train_loss": train_history,
             "val_loss": val_history,
             "cumulative_time_seconds": epoch_times}).to_csv(
                 model_dir / f"{model_name}_loss_history.csv", index = False)


#python -m model_training.meshgraphnet (after activating venv)