#this functions file is for the GNN/MeshGraphNet

import pandas as pd
import torch
import numpy as np
from torch_geometric.data import Data
import torch.nn as nn
from torch_geometric.utils import scatter
from torch.utils.data import Dataset
from pathlib import Path



def build_edges(sample, edges):
    """Builds directed edges and edge features from a sample and its edges."""

    label_to_index = pd.Series(
    sample.index.to_numpy(), index = sample["node_label"].to_numpy(),
    )

    sender_indices = label_to_index.loc[edges["node_label_1"].to_numpy()].to_numpy()
    receiver_indices = label_to_index.loc[edges["node_label_2"].to_numpy()].to_numpy()

    positions = sample[["x", "y", "z"]].to_numpy()

    sender_positions = positions[sender_indices]
    receiver_positions = positions[receiver_indices]

    displacement = receiver_positions - sender_positions
    distance = np.linalg.norm(displacement, axis = 1, keepdims = True)

    forward_edge_attr = np.concatenate([displacement, distance], axis = 1)
    reverse_edge_attr = np.concatenate([-displacement, distance], axis = 1)

    forward_edge_index = np.stack([sender_indices, receiver_indices], axis = 0)
    reverse_edge_index = np.stack([receiver_indices, sender_indices], axis = 0)

    edge_index = np.concatenate([forward_edge_index, reverse_edge_index], axis = 1)
    edge_attr = np.concatenate([forward_edge_attr, reverse_edge_attr], axis = 0)

    edge_index = torch.as_tensor(edge_index, dtype = torch.long)
    edge_attr = torch.as_tensor(edge_attr, dtype = torch.float32)

    return edge_index, edge_attr



def build_graph(
    sample,
    edges,
    feature_columns,
    feature_values=None,
):
    """
    Builds one PyTorch Geometric graph.

    Edge features are calculated from the raw physical coordinates in
    `sample`. Node features can be supplied separately through
    `feature_values`, allowing them to be standardized without changing
    the physical coordinates used for edge construction.
    """

    sample = sample.reset_index(
        drop=True
    )

    # This uses the raw x, y and z coordinates from the CSV.
    edge_index, edge_attr = build_edges(
        sample,
        edges,
    )

    # If prepared node features were not provided, use the raw feature
    # columns. This keeps unstandardized datasets usable.
    if feature_values is None:
        feature_values = sample[
            feature_columns
        ].to_numpy(
            dtype=np.float32,
            copy=True,
        )

    else:
        feature_values = np.asarray(
            feature_values,
            dtype=np.float32,
        )

    x = torch.as_tensor(
        feature_values,
        dtype=torch.float32,
    )

    y = torch.as_tensor(
        sample[
            "peak_temperature"
        ].to_numpy(
            dtype=np.float32,
            copy=True,
        ),
        dtype=torch.float32,
    )

    data = Data(
        x=x,
        edge_index=edge_index,
        edge_attr=edge_attr,
        y=y,
    )

    num_nodes = sample.shape[0]
    num_edges = edge_index.shape[1]

    assert x.shape == (
        num_nodes,
        len(feature_columns),
    )

    assert y.shape == (
        num_nodes,
    )

    assert edge_index.shape == (
        2,
        num_edges,
    )

    assert edge_attr.shape == (
        num_edges,
        4,
    )

    assert edge_index.min() >= 0
    assert edge_index.max() < num_nodes

    assert torch.isfinite(x).all()
    assert torch.isfinite(y).all()
    assert torch.isfinite(edge_attr).all()

    return data

class MLP(nn.Module):
    def __init__(self, input_size: int, latent_size: int, output_size: int, use_layer_norm: bool = True):
        super().__init__()
        self.linear1 = nn.Linear(input_size, latent_size)
        self.linear2 = nn.Linear(latent_size, latent_size)
        self.linear3 = nn.Linear(latent_size, output_size)
        self.relu = nn.ReLU()

        if use_layer_norm:
            self.norm = nn.LayerNorm(output_size)

        else:
            self.norm = nn.Identity()

    def forward(self, x):
        x = self.relu(self.linear1(x))
        x = self.relu(self.linear2(x))
        x = self.linear3(x)
        x = self.norm(x)
        return x


class ProcessorBlock(nn.Module):
    def __init__(self, latent_size: int, use_layer_norm: bool = True):
        super().__init__()
        self.edge_mlp = MLP(3*latent_size, latent_size, latent_size, use_layer_norm)
        self.node_mlp = MLP(2*latent_size, latent_size, latent_size, use_layer_norm)

    def forward(self, node_latent, edge_latent, edge_index):
        senders = edge_index[0]
        receivers = edge_index[1]

        sender_latent = node_latent[senders]
        receiver_latent = node_latent[receivers]
    
        edge_mlp_input = torch.cat([edge_latent, sender_latent, receiver_latent], dim = -1)

        edge_delta = self.edge_mlp(edge_mlp_input)

        updated_edge_latent = edge_latent + edge_delta

        aggregated = scatter(reduce = "sum",
                             src = updated_edge_latent,
                             index = receivers,
                             dim = 0,
                             dim_size = node_latent.shape[0])
        
        node_mlp_input = torch.cat([node_latent, aggregated], dim = -1)

        node_delta = self.node_mlp(node_mlp_input)

        updated_node_latent = node_latent + node_delta

        return updated_node_latent, updated_edge_latent



class MeshGraphNet(nn.Module):

    def __init__(self, node_input_size: int, edge_input_size: int = 4, latent_size: int = 128, num_processor_blocks: int = 10, use_layer_norm: bool = True):
        super().__init__()
        self.node_encoder = MLP(node_input_size, latent_size, latent_size, use_layer_norm)
        self.edge_encoder = MLP(edge_input_size, latent_size, latent_size, use_layer_norm)
        self.processor_blocks = nn.ModuleList([ProcessorBlock(latent_size) for _ in range(num_processor_blocks)])
        self.decoder = MLP(latent_size, latent_size, 1, use_layer_norm = False)


    def forward(self, data):
        node_latent = self.node_encoder(data.x)
        edge_latent = self.edge_encoder(data.edge_attr)

        for block in self.processor_blocks:
            node_latent, edge_latent = block(node_latent, edge_latent, data.edge_index)

        prediction = self.decoder(node_latent)

        return prediction.squeeze(-1)
    


def train_one_epoch(model, loader, optimizer, loss_function, device, accumulation_steps = 1):
    """
    Performs one epoch of training on the given data loader.
    """
    model.train()
    total_loss = 0.0
    total_nodes = 0
    
    for batch_index, batch in enumerate(loader):
        batch = batch.to(device)
        optimizer.zero_grad()

        prediction = model(batch)
        train_loss = loss_function(prediction, batch.y)

        scaled_loss = train_loss / accumulation_steps
        scaled_loss.backward()

        step_optimizer = (
            (batch_index + 1) % accumulation_steps == 0 or batch_index + 1 == len(loader)
        )

        if step_optimizer:
            optimizer.step()
            optimizer.zero_grad(set_to_none = True)

        num_nodes = batch.y.numel()
        total_loss += train_loss.item()*num_nodes
        total_nodes += num_nodes

    mean_loss = total_loss / total_nodes

    return mean_loss


def evaluate(model, loader, loss_function, device):
    """
    Evaluates the model on the given data loader.
    """
    model.eval()

    total_loss = 0.0
    total_nodes = 0

    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)

            prediction = model(batch)
            val_loss = loss_function(prediction, batch.y)

            

            num_nodes = batch.y.numel()

            total_loss += val_loss.item() * num_nodes
            total_nodes += num_nodes

    mean_loss = total_loss / total_nodes

    return mean_loss

class MeshDataset(Dataset):
    """
    Loads mesh samples and optionally standardizes selected node-feature
    columns using externally calculated statistics.

    The statistics should be calculated from the complete training split
    and reused for training, validation and testing.
    """

    def __init__(
        self,
        root_directory,
        feature_mean=None,
        feature_std=None,
        standardized_columns=None,
    ):
        self.root_directory = Path(
            root_directory
        )

        self.non_feature_columns = {
            "sample",
            "node_label",
            "peak_temperature",
        }

        # Include only directories containing both required CSV files.
        self.sample_directories = sorted(
            directory
            for directory in self.root_directory.iterdir()
            if directory.is_dir()
            and (
                directory
                / "{}.csv".format(directory.name)
            ).is_file()
            and (
                directory
                / "{}_edges.csv".format(directory.name)
            ).is_file()
        )

        if len(self.sample_directories) == 0:
            raise ValueError(
                "No complete sample directories found in {}".format(
                    self.root_directory
                )
            )

        self.node_filenames = [
            directory.name + ".csv"
            for directory in self.sample_directories
        ]

        self.edge_filenames = [
            directory.name + "_edges.csv"
            for directory in self.sample_directories
        ]

        # Read only the first CSV header to determine the feature schema.
        first_node_path = (
            self.sample_directories[0]
            / self.node_filenames[0]
        )

        first_columns = pd.read_csv(
            first_node_path,
            nrows=0,
        ).columns.tolist()

        self.feature_columns = [
            column
            for column in first_columns
            if column not in self.non_feature_columns
        ]

        if len(self.feature_columns) == 0:
            raise ValueError(
                "No node-feature columns found in {}".format(
                    first_node_path
                )
            )

        self.num_features = len(
            self.feature_columns
        )

        self.standardized_columns = (
            []
            if standardized_columns is None
            else list(standardized_columns)
        )

        unknown_columns = (
            set(self.standardized_columns)
            - set(self.feature_columns)
        )

        if unknown_columns:
            raise ValueError(
                "Requested standardization for unknown columns: {}".format(
                    sorted(unknown_columns)
                )
            )

        # No normalization statistics were supplied.
        if (
            feature_mean is None
            and feature_std is None
        ):
            if self.standardized_columns:
                raise ValueError(
                    "Standardized columns were provided without "
                    "feature means and standard deviations."
                )

            self.feature_mean = None
            self.feature_std = None

        # Only one of mean/std was supplied.
        elif (
            feature_mean is None
            or feature_std is None
        ):
            raise ValueError(
                "feature_mean and feature_std must either both be "
                "provided or both be omitted."
            )

        else:
            self.feature_mean = pd.Series(
                feature_mean,
                dtype=np.float64,
            )

            self.feature_std = pd.Series(
                feature_std,
                dtype=np.float64,
            )

            missing_statistics = (
                set(self.standardized_columns)
                - set(self.feature_mean.index)
            )

            missing_statistics |= (
                set(self.standardized_columns)
                - set(self.feature_std.index)
            )

            if missing_statistics:
                raise ValueError(
                    "Missing normalization statistics for: {}".format(
                        sorted(missing_statistics)
                    )
                )

            invalid_standard_deviations = [
                column
                for column in self.standardized_columns
                if (
                    not np.isfinite(
                        self.feature_std[column]
                    )
                    or self.feature_std[column] <= 0.0
                )
            ]

            if invalid_standard_deviations:
                raise ValueError(
                    "Invalid standard deviations for: {}".format(
                        sorted(invalid_standard_deviations)
                    )
                )

    def __len__(self):
        return len(
            self.sample_directories
        )

    def __getitem__(self, index):
        sample_directory = (
            self.sample_directories[index]
        )

        node_path = (
            sample_directory
            / self.node_filenames[index]
        )

        edge_path = (
            sample_directory
            / self.edge_filenames[index]
        )

        # This DataFrame remains unchanged and retains physical values.
        node_df = pd.read_csv(
            node_path
        )

        edge_df = pd.read_csv(
            edge_path
        )

        current_feature_columns = [
            column
            for column in node_df.columns
            if column not in self.non_feature_columns
        ]

        if (
            current_feature_columns
            != self.feature_columns
        ):
            raise ValueError(
                "Feature schema mismatch in {}.\n"
                "Expected: {}\n"
                "Received: {}".format(
                    node_path,
                    self.feature_columns,
                    current_feature_columns,
                )
            )

        # Create a separate copy for node inputs. Standardizing this
        # copy does not affect the raw coordinates in node_df.
        feature_df = node_df[
            self.feature_columns
        ].copy()

        if self.feature_mean is not None:
            feature_df.loc[
                :,
                self.standardized_columns,
            ] = (
                feature_df[
                    self.standardized_columns
                ]
                - self.feature_mean[
                    self.standardized_columns
                ]
            ) / self.feature_std[
                self.standardized_columns
            ]

        feature_values = feature_df.to_numpy(
            dtype=np.float32,
            copy=True,
        )

        if not np.isfinite(
            feature_values
        ).all():
            raise ValueError(
                "Nonfinite node features found in {}".format(
                    node_path
                )
            )

        graph = build_graph(
            sample=node_df,
            edges=edge_df,
            feature_columns=self.feature_columns,
            feature_values=feature_values,
        )

        graph.sample_name = (
            sample_directory.name
        )

        return graph


def compute_feature_statistics(
    dataset,
    feature_columns,
    chunksize=200_000,
):
    """
    Computes node-weighted feature means and standard deviations from
    the dataset's CSV files.

    This should be called only on the training dataset.
    """

    feature_sum = pd.Series(
        0.0,
        index=feature_columns,
        dtype=np.float64,
    )

    feature_squared_sum = pd.Series(
        0.0,
        index=feature_columns,
        dtype=np.float64,
    )

    total_rows = 0

    for sample_directory in dataset.sample_directories:
        node_path = (
            sample_directory
            / "{}.csv".format(sample_directory.name)
        )

        for chunk in pd.read_csv(
            node_path,
            usecols=feature_columns,
            chunksize=chunksize,
        ):
            values = chunk.astype(
                np.float64
            )

            feature_sum += values.sum(
                axis=0
            )

            feature_squared_sum += (
                values ** 2
            ).sum(
                axis=0
            )

            total_rows += len(values)

    if total_rows == 0:
        raise ValueError(
            "No rows found while calculating feature statistics."
        )

    feature_mean = (
        feature_sum
        / total_rows
    )

    feature_variance = (
        feature_squared_sum
        / total_rows
        - feature_mean ** 2
    )

    # Remove tiny negative values that can appear through floating-point
    # arithmetic.
    feature_variance = feature_variance.clip(
        lower=0.0
    )

    feature_std = np.sqrt(
        feature_variance
    )

    # A constant feature cannot be divided by its standard deviation.
    # Setting its scale to 1 leaves its centered value at zero.
    feature_std[
        feature_std < 1e-8
    ] = 1.0

    return feature_mean, feature_std