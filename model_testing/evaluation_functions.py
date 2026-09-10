
import matplotlib.pyplot as plt

import numpy as np
import torch
import time
import pyvista as pv

pv.set_jupyter_backend("trame")

def plot_each_test_graph(model, dataset, device):
    """
    Plots predicted versus true peak temperatures for each sample in the dataset on 
    its own plot."""
    model.eval()

    with torch.no_grad():
        for graph_index, graph in enumerate(dataset):
            graph_device = graph.clone().to(device)

            predictions = model(graph_device).reshape(-1).cpu()
            targets = graph.y.reshape(-1).cpu()

            minimum = min(targets.min().item(), predictions.min().item())
            maximum = max(targets.max().item(), predictions.max().item())

            plt.figure(figsize=(6, 6))
            plt.scatter(
                targets.numpy(),
                predictions.numpy(),
                s=5,
                alpha=0.25, color = "firebrick"
            )

            plt.plot(
                [minimum, maximum],
                [minimum, maximum],
                linestyle="--", c = "royalblue",
        label="Perfect prediction"
            )

            plt.xlabel("True peak temperature")
            plt.ylabel("Predicted peak temperature")
            plt.legend()
            plt.title(
                f"{graph.sample_name} — predictions versus targets"
            )
            plt.axis("equal")
            plt.show()


def calculate_dataset_target_mean(dataset):
    """calculate the mean of the values in a dataset"""
    total = 0.0
    count = 0

    for graph in dataset:
        total += graph.y.sum().item()
        count += graph.y.numel()

    return total / count


def evaluate_model_and_mean_baseline(
    model,
    dataset,
    device,
    training_mean,
):
    """evaluate the model on a dataset and print the evaluation metrics of each sample."""

    model.eval()

    all_targets = []
    all_predictions = []

    with torch.no_grad():
        for graph in dataset:
            graph = graph.to(device)

            # Adjust this line to match your model's forward method.
            predictions = model(graph)

            predictions = predictions.reshape(-1)
            targets = graph.y.reshape(-1)

            all_predictions.append(predictions.cpu())
            all_targets.append(targets.cpu())

    predictions = torch.cat(all_predictions)
    targets = torch.cat(all_targets)

    model_mse = torch.mean((predictions - targets) ** 2)

    mean_predictions = torch.full_like(
        targets,
        fill_value=training_mean,
    )

    baseline_mse = torch.mean(
        (mean_predictions - targets) ** 2
    )

    correlation = torch.corrcoef(
        torch.stack([predictions, targets])
    )[0, 1]

    print(f"Model MSE:         {model_mse.item():.4f}")
    print(f"Mean baseline MSE: {baseline_mse.item():.4f}")
    print(f"Target std:        {targets.std().item():.4f}")
    print(f"Prediction std:    {predictions.std().item():.4f}")
    print(f"Correlation:       {correlation.item():.4f}")

    return targets, predictions





def plot_model_prediction_vs_target(targets, predictions):
    """
    Plot the model's predictions versus the true targets for all samples on a single plot.
    """
    minimum = min(targets.min().item(), predictions.min().item())
    maximum = max(targets.max().item(), predictions.max().item())

    plt.figure(figsize=(6, 6))
    plt.plot(
        [minimum, maximum],
        [minimum, maximum],
        linestyle="--", c = "royalblue",
        label="Perfect prediction"
    )
    plt.scatter(
        targets.numpy(),
        predictions.numpy(),
        s=4,
        alpha=0.01, color = "firebrick"
    )





    plt.xlabel("True peak temperature (°C)")
    plt.ylabel("Predicted peak temperature (°C)")
    #plt.title("Predictions versus targets")
    plt.legend()
    plt.show()

    mse = np.mean((predictions.numpy() - targets.numpy()) ** 2)
    rmse = np.sqrt(mse)

    print("Plot MSE:", mse)
    print("Plot RMSE:", rmse)

    print("VAL")
    #print("loss:", loss.item())
    print("target min/max/mean/std:",
        targets.numpy().min().item(),
        targets.numpy().max().item(),
        targets.numpy().mean().item(),
        targets.numpy().std().item())

    print("pred min/max/mean/std:",
        predictions.numpy().min().item(),
        predictions.numpy().max().item(),
        predictions.numpy().mean().item(),
        predictions.numpy().std().item())



def evaluate_split(model, test_loader, metadata_df):
    """evaluates and prints relevant metrics for all samples in a split of the dataset."""
    all_percent_errors = []
    all_names = []
    num_nodes = []
    loss = []
    loss_percent = []
    model_time_percent = []

    with torch.no_grad():
        for batch in test_loader:

            start_time = time.time()
            prediction = model(batch)

            prediction_time = time.time() - start_time

            if metadata_df is not None:

                abaqus_solve_time = metadata_df.loc[batch.sample_name[0], "abaqus_solve_time"]
            
                error = prediction - batch.y

                mean_temp = batch.y.mean().item()
                mse = error.square().mean().item()
                rmse = error.square().mean().sqrt().item()
                mae = error.abs().mean().item()
                max_error = error.abs().max().item()
                mean_percent_error = error.abs().mean().item() / mean_temp * 100
                percent_error = error.abs() /mean_temp * 100

                all_names.append(batch.sample_name[0])
                all_percent_errors.append(percent_error)
                loss.append(mse)
                num_nodes.append(batch.y.shape[0])
                model_time_percent.append(prediction_time / abaqus_solve_time)
                loss_percent.append(mean_percent_error)

                print(f"{batch.sample_name}:  \n" 
                    f"MSE = {mse:.4f} | "
                    f"RMSE = {rmse:.4f} | "
                    f"MAE = {mae:.4f} | "
                    f"Max Error = {max_error:.4f} | "
                    f"Mean Percent Error = {mean_percent_error:.4f}% \n"
                    f"Abaqus solve time = {abaqus_solve_time:.2f} seconds | "
                    f"MeshGraphNet prediction time = {prediction_time:.2f} seconds | "
                    f"Prediction speedup = {((abaqus_solve_time - prediction_time)/abaqus_solve_time * 100):.2f}% \n"
                    )

            else:               
                    error = prediction - batch.y
    
                    mean_temp = batch.y.mean().item()
                    mse = error.square().mean().item()
                    rmse = error.square().mean().sqrt().item()
                    mae = error.abs().mean().item()
                    max_error = error.abs().max().item()
                    mean_percent_error = error.abs().mean().item() / mean_temp * 100
                    percent_error = error.abs() /mean_temp * 100
    
                    all_names.append(batch.sample_name[0])
                    all_percent_errors.append(percent_error)
                    loss.append(mse)
                    num_nodes.append(batch.y.shape[0])
                    loss_percent.append(mean_percent_error)
    
                    print(f"{batch.sample_name}:  \n" 
                        f"MSE = {mse:.4f} | "
                        f"RMSE = {rmse:.4f} | "
                        f"MAE = {mae:.4f} | "
                        f"Max Error = {max_error:.4f} | "
                        f"Mean Percent Error = {mean_percent_error:.4f}% \n"
                        f"MeshGraphNet prediction time = {prediction_time:.2f} seconds | "
                        )




def plot_pv_field(model, graph, device, plot = "error", plot_abs = False):
    """
    Plots fields in 3D for a given graph.
    
    valid arguments for plot:
    'target': ground truth for this geometry
    'prediction': model prediction for this geometry
    'error': difference between prediction and ground truth
    
    'plot_abs' must be false for 'target' and 'prediction' plots.
    """
    model.eval()

    plot = plot.lower()

    graph_device = graph.clone().to(device)

    with torch.no_grad():
        predictions = model(graph_device).reshape(-1).cpu()

    targets = graph.y.reshape(-1).cpu()
    residuals = predictions - targets
    

    points = graph.x[:, :3].detach().cpu().numpy()

    cloud = pv.PolyData(points)

    cloud["target"] = targets.numpy()
    cloud["prediction"] = predictions.numpy()
    cloud["residual"] = residuals.numpy()
    cloud["absolute_error"] = residuals.abs().numpy()

    plotter = pv.Plotter()

    clim = residuals.abs().max().item()

    

    if plot == "error":
        title = "Prediction - target"
        scalars = "residual"

    elif plot == "target":
        title = "Target"
        scalars = "target"

    elif plot == "prediction":
        title = "Prediction"
        scalars = "prediction"

    else:
        raise ValueError(
            "plot must be one of 'error', 'target', 'prediction', got {}".format(plot)
        )

    

    if plot_abs and plot != "error":
        raise ValueError(
            f"plot_abs is only available for plot='error', got {plot}"
        )

    if plot_abs:
        scalars = "absolute_error"
        title = f"abs({title}) [°C]"
        lowerlim = 0
        cmap = "viridis"
    else:
        lowerlim = -clim
        title = f"{title} [°C]"
        cmap = "coolwarm"


    sargs = dict(
            title = title,
            vertical=False,
            width=0.5,
            height=0.1,
            position_x=0.25,
            position_y=0.05,  # near the bottom
        )

    
    if plot == "error":
        plotter.add_mesh(
            cloud,
            scalars=scalars,
            render_points_as_spheres=True,
            point_size=5,
            cmap=cmap,
            clim=[
                lowerlim,
                clim,
            ],
            scalar_bar_args=sargs,
        )
    else:
        plotter.add_mesh(
                    cloud,
                    scalars=scalars,
                    render_points_as_spheres=True,
                    point_size=5,
                    cmap=cmap,
                    scalar_bar_args=sargs,
                )
        

    plotter.add_axes()
    plotter.show_grid()
    plotter.show()