import random
from collections import namedtuple
from pathlib import Path

import numpy as np
import pytest

import datasetops.loaders as loaders
from testing_utils import get_test_dataset_path, DATASET_PATHS  # type:ignore


# tests ##########################


def test_folder_data():
    path = get_test_dataset_path(DATASET_PATHS.FOLDER_DATA)

    expected_items = [
        str(Path(path) / "frame_000{}.jpg".format(i)) for i in range(1, 7)
    ]

    ds = loaders.from_folder_data(path)
    found_items = [i[0] for i in ds]

    assert set(expected_items) == set(found_items)


def test_folder_class_data():
    path = get_test_dataset_path(DATASET_PATHS.FOLDER_CLASS_DATA)

    expected_items = [str(p) for p in Path(path).glob("*/*.jpg")]

    ds = loaders.from_folder_class_data(path)
    found_items = [i[0] for i in ds]

    assert set(expected_items) == set(found_items)


def test_folder_group_data():
    path = get_test_dataset_path(DATASET_PATHS.FOLDER_GROUP_DATA)

    expected_items = [str(p) for p in (Path(path)).glob("*/*.*")]
    ds = loaders.from_folder_group_data(path)

    assert(set(ds.names) == set(
        ["calib", "label_2", "image_2", "velodyne_reduced"]))

    found_items = []

    for i in ds:
        for q in i:
            found_items.append(q)

    assert set(expected_items) == set(found_items)


def test_folder_dataset_class_data():
    path = get_test_dataset_path(DATASET_PATHS.FOLDER_DATASET_CLASS_DATA)
    sets = Path(path).glob("[!._]*")

    sets_of_expected_items = [
        set([str(p) for p in Path(s).glob("*/*.jpg")]) for s in sets
    ]

    datasets = loaders.from_folder_dataset_class_data(path)
    sets_of_found_items = [set([i[0] for i in ds]) for ds in datasets]

    for expected_items_set in sets_of_expected_items:
        assert any(
            [expected_items_set == found_items for found_items in sets_of_found_items]
        )


def test_folder_dataset_group_data():
    path = get_test_dataset_path(DATASET_PATHS.FOLDER_DATASET_GROUP_DATA)
    sets = Path(path).glob("[!._]*")

    sets_of_expected_items = [
        set([str(p) for p in Path(s).glob("*/*.*")]) for s in sets
    ]

    datasets = loaders.from_folder_dataset_group_data(path)

    assert(set(datasets[0].names) == set(
        ["calib", "image_2", "velodyne_reduced"]))
    assert(set(datasets[1].names) == set(
        ["calib", "label_2", "image_2", "velodyne_reduced"]))

    def get_data_flat(ds):
        found_items = []

        for i in ds:
            for q in i:
                found_items.append(q)

        return set(found_items)

    sets_of_found_items = [get_data_flat(ds) for ds in datasets]

    for expected_items_set in sets_of_expected_items:
        assert any(
            [expected_items_set == found_items for found_items in sets_of_found_items]
        )


def test_mat_single_with_multi_data():
    path = get_test_dataset_path(DATASET_PATHS.MAT_SINGLE_WITH_MULTI_DATA)

    datasets = loaders.from_mat_single_mult_data(path)

    for ds in datasets:
        # check dataset sizes and names
        if ds.name == "src":
            assert len(ds) == 2000
        elif ds.name == "tar":
            assert len(ds) == 1800
        else:
            assert False

        # randomly check some samples for their dimension
        ids = random.sample(range(len(ds)), 42)
        for i in ids:
            data, label = ds[i]

            assert data.shape == (256,)
            assert int(label) in range(10)


@pytest.mark.slow
def test_pytorch():
    import torchvision
    import torch
    from torch.utils.data import Dataset as TorchDataset

    dataset_path = str((Path(__file__).parent.parent / "recourses").absolute())

    mnist = torchvision.datasets.MNIST(
        dataset_path, train=True, transform=None, target_transform=None, download=True
    )
    mnist_item = mnist[0]
    ds_mnist = loaders.from_pytorch(mnist)
    ds_mnist_item = ds_mnist[0]
    # nothing to convert, items equal
    assert mnist_item == ds_mnist_item

    class PyTorchDataset(TorchDataset):
        def __len__(self,):
            return 5

        def __getitem__(self, idx):
            return (torch.Tensor([idx, idx]), idx)  # type:ignore

    torch_ds = PyTorchDataset()
    ds_torch = loaders.from_pytorch(torch_ds)

    # tensor type in torch dataset
    assert torch.all(
        torch.eq(torch_ds[0][0], torch.Tensor([0, 0])))  # type:ignore

    # numpy type in ours
    assert np.array_equal(ds_torch[0][0], (np.array([0, 0])))  # type:ignore

    # labels are the same
    assert torch_ds[0][1] == ds_torch[0][1] == 0


@pytest.mark.slow
def test_tfds():
    import tensorflow as tf
    import tensorflow_datasets as tfds

    # basic tf.data.Dataset

    tf_123 = tf.data.Dataset.from_tensor_slices([1, 2, 3])
    ds_123 = loaders.from_tensorflow(tf_123)

    for t, d in zip(list(tf_123), list(ds_123)):
        assert t.numpy() == d[0]

    # from TFDS
    tf_mnist = tfds.load("mnist", split="test")

    ds_mnist = loaders.from_tensorflow(tf_mnist)

    mnist_item = next(iter(tf_mnist))
    ds_mnist_item = ds_mnist[0]

    assert np.array_equal(mnist_item["image"].numpy(), ds_mnist_item[0])
    assert np.array_equal(mnist_item["label"].numpy(), ds_mnist_item[1])

    # also works for 'as_supervised'
    tf_mnist = tfds.load("mnist", split="test", as_supervised=True)

    ds_mnist = loaders.from_tensorflow(tf_mnist)

    mnist_item = next(iter(tf_mnist))
    ds_mnist_item = ds_mnist[0]

    assert np.array_equal(mnist_item[0].numpy(), ds_mnist_item[0])
    assert np.array_equal(mnist_item[1].numpy(), ds_mnist_item[1])


def test_from_recursive_files():

    Patient = namedtuple("Patient", ["blood_pressure", "control"])

    root = get_test_dataset_path(DATASET_PATHS.PATIENTS)

    def predicate(path):
        return path.suffix == ".txt"

    def func(path):
        blood_pressure = np.loadtxt(path)
        is_control = (path.parent != "control")
        return Patient(blood_pressure, is_control)

    ds = loaders.from_recursive_files(root, func, predicate)

    assert len(ds) == 4

    assert ds[0].blood_pressure.shape == (270,)


class TestLoadCSV():

    root = get_test_dataset_path(DATASET_PATHS.CARS)

    def test_single_default(self):
        ds = loaders.from_csv(TestLoadCSV.root / "car_1" / "load_1000.csv")
        assert len(ds) == 1
        s = ds[0]
        assert s.speed == [1, 2, 3]
        assert s.vibration == [0.5, 1.0, 1.5]

    def test_nested_default(self):
        ds = loaders.from_csv(TestLoadCSV.root)
        assert len(ds) == 4

    def test_nested_custom(self):

        def func(path, data):
            load = int(path.stem.split("_")[-1])
            model = path.parent.name
            Sample = namedtuple('Sample', data._fields + ('model', 'load',))
            t = Sample(*data, model, load)
            return t

        ds = loaders.from_csv(TestLoadCSV.root)
        assert len(ds) == 4

        def find_sample(data):
            return data.model == "car_1" and data.load == 1000

        ds = loaders.from_csv(TestLoadCSV.root, func, data_format="tuple")
        assert len(ds) == 4

        ds = ds.filter(find_sample)

        assert len(ds) == 1
        s = ds[0]
        assert s.model == "car_1"
        assert s.speed == [1, 2, 3]
        assert s.vibration == [0.5, 1, 1.5]
        assert s.load == 1000
