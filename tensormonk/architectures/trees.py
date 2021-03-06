""" TensorMONK :: architectures """

import torch
import torch.nn as nn
import numpy as np
import torch.nn.functional as F
from ..layers import Linear


class NeuralTree(nn.Module):
    r""" A neural tree for Neural Decision Forest!

    Args:
        tensor_size: shape of 2D/4D tensor
            2D - (None/any integer, features)
            4D - (None/any integer, channels, height, width)
        n_labels: number of labels or classes
        depth: depth of trees
                Ex: linear layer indices for a tree of depth = 2
                    0
                  1   2
                 3 4 5 6
                a linear requries 7 output neurons (2**(depth+1) - 1)
        dropout: 0. - 1., default = 0.2
        network = any custom torch module can be used to produce leaf outputs
            (must have output neurons of length 2**(depth+1)-1)
            when None, linear + relu + dropout + linear + sigm

    Return:
        decision (a torch.Tensor), predictions (a torch.Tensor)
    """
    def __init__(self,
                 tensor_size: tuple,
                 n_labels: int,
                 depth: int,
                 dropout: float = 0.2,
                 network: torch.nn.Module = None):
        super(NeuralTree, self).__init__()

        assert depth > 0, \
            "NeuralTree :: depth must be > 0, given {}".format(depth)

        self.tensor_size = tensor_size
        self.n_labels = n_labels
        self.depth = depth
        self.n_leafs = 2**(depth+1)

        # dividing the linear output to decisions at different levels
        self.decision_per_depth = [2**x for x in range(depth+1)]
        # their indices
        self.indices_per_depth = [list(range(y-x, max(1, y))) for x, y in
                                  zip(self.decision_per_depth,
                                      np.cumsum(self.decision_per_depth))]

        # an example - can be any number of layers
        hidden = (self.n_leafs+1)*4
        self.tree = nn.Sequential(
            Linear(tensor_size, hidden, "relu", dropout),
            Linear((None, hidden), self.n_leafs-1, "sigm", dropout)) \
            if network is None else network

        self.weight = nn.Parameter(torch.randn(self.n_leafs, n_labels))
        self.weight.data.normal_(0, 0.02)
        self.tensor_size = (None, n_labels)

    def forward(self, tensor):
        if tensor.dim() > 2:
            tensor = tensor.view(tensor.size(0), -1)
        BSZ = tensor.size(0)
        # get all leaf responses -- a simple linear layer
        leaf_responses = self.tree(tensor)
        # compute decisions from the final depth
        decision = leaf_responses[:, self.indices_per_depth[0]]
        for x in self.indices_per_depth[1:]:
            decision = decision.unsqueeze(2)
            # true and false of last depth
            decision = torch.cat((decision, 1 - decision), 2).view(BSZ, -1)
            # current depth decisions
            decision = decision.mul(leaf_responses[:, x])
        decision = decision.unsqueeze(2)
        decision = torch.cat((decision, 1 - decision), 2).view(BSZ, -1)
        # predictions
        predictions = decision.unsqueeze(2)
        predictions = predictions.mul(F.softmax(self.weight, 1).unsqueeze(0))
        return decision, predictions.sum(1)


# from tensormonk.layers import Linear
# test = NeuralTree((1, 64), 12, 4)
# decision, predictions = test(torch.randn(1, 64))
# decision.shape
# predictions.shape


class NeuralDecisionForest(nn.Module):
    r"""Neural Decision Forest!
    A version of https://ieeexplore.ieee.org/document/7410529

    Args:
        tensor_size: shape of 2D/4D tensor
            2D - (None/any integer, features)
            4D - (None/any integer, channels, height, width)
        n_labels: number of labels or classes
        n_trees: number of trees
        depth: depth of trees
                Ex: linear layer indices for a tree of depth = 2
                    0
                  1   2
                 3 4 5 6
                a linear requries 7 output neurons (2**(depth+1) - 1)
        dropout: 0. - 1., default = 0.2
        network = any custom torch module can be used to produce leaf outputs
            (must have output neurons of length 2**(depth+1)-1)
            when None, linear + relu + dropout + linear + sigm

    Return:
        decision (a torch.Tensor), predictions (a torch.Tensor)
    """
    def __init__(self,
                 tensor_size: tuple,
                 n_labels: int,
                 n_trees: int,
                 depth: int,
                 dropout: float = 0.2,
                 network: torch.nn.Module = None):
        super(NeuralDecisionForest, self).__init__()

        self.trees = nn.ModuleList([NeuralTree(tensor_size, n_labels, depth,
                                               dropout, network)
                                    for i in range(n_trees)])
        self.tensor_size = self.trees[0].tensor_size

    def forward(self, tensor):
        if tensor.dim() > 2:
            tensor = tensor.view(tensor.size(0), -1)
        decisions, predictions = [], []
        for tree in self.trees:
            decision, prediction = tree(tensor)
            decisions.append(decision)
            predictions.append(prediction.unsqueeze(2))
        decisions = torch.cat(decisions, 1)
        predictions = torch.cat(predictions, 2)
        return decisions[:, 0::2], predictions.mean(2).log()


# test = NeuralDecisionForest((1, 256), 6, 8, 5)
# decisions, predictions = test(torch.rand(1, 256))
# %timeit decisions, predictions = test(torch.rand(1, 256))
# np.sum([p.numel() for p in test.parameters()])
# decisions.shape
