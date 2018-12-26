""" TensorMONK's :: NeuralArchitectures                                     """

import torch
from ..NeuralLayers import Convolution, ResidualInverted, Linear


class MobileNetV2(torch.nn.Sequential):
    r"""MobileNetV2 implemented from https://arxiv.org/pdf/1801.04381.pdf
    Designed for input size of (1, 1/3, 224, 224), works for
    min(height, width) >= 128

    Args:
        tensor_size: shape of tensor in BCHW
            (None/any integer >0, channels, height, width)
        activation: None/relu/relu6/lklu/elu/prelu/tanh/sigm/maxo/rmxo/swish
        normalization: None/batch/group/instance/layer/pixelwise
        pre_nm: if True, normalization -> activation -> convolution else
            convolution -> normalization -> activation
        groups: grouped convolution, value must be divisble by tensor_size[1]
            and out_channels, default = 1
        weight_nm: True/False, default = False
        equalized: True/False, default = False
        shift: True/False, default = False
            Shift replaces 3x3 convolution with pointwise convs after shifting.
            Requires tensor_size[1] >= 9 and filter_size = 3
        n_embedding: when not None and > 0, adds a linear layer to the network
            and returns a torch.Tensor of shape (None, n_embedding)
    """
    def __init__(self,
                 tensor_size=(6, 3, 224, 224),
                 activation: str = "relu",
                 normalization: str = "batch",
                 pre_nm: bool = False,
                 weight_nm: bool = False,
                 equalized: bool = False,
                 shift: bool = False,
                 n_embedding: int = None,
                 *args, **kwargs):
        super(MobileNetV2, self).__init__()

        block_params = [(16, 1, 1), (24, 2, 6), (24, 1, 6), (32, 2, 6),
                        (32, 1, 6), (32, 1, 6), (64, 2, 6), (64, 1, 6),
                        (64, 1, 6), (64, 1, 6), (96, 1, 6), (96, 1, 6),
                        (96, 1, 6), (160, 2, 6), (160, 1, 6), (160, 1, 6),
                        (320, 1, 6)]

        kwargs = {"activation": activation, "normalization": normalization,
                  "weight_nm": weight_nm, "equalized": equalized,
                  "shift": shift, "groups": 1, "pad": True}

        print("Input", tensor_size)
        self.add_module("ConvolutionFirst",
                        Convolution(tensor_size, 3, 32, 2, pre_nm=False,
                                    **kwargs))
        t_size = self.ConvolutionFirst.tensor_size
        print("ConvolutionFirst", t_size)

        for i, (oc, s, t) in enumerate(block_params):
            self.add_module("ResidualInverted"+str(i),
                            ResidualInverted(t_size, 3, oc, s, t=t,
                                             pre_nm=False if i == 0 else
                                             pre_nm, **kwargs))
            t_size = getattr(self, "ResidualInverted"+str(i)).tensor_size
            print("ResidualInverted"+str(i), t_size)

        self.add_module("ConvolutionLast",
                        Convolution(t_size, 1, 1280, 1, pre_nm=pre_nm,
                                    **kwargs))
        t_size = self.ConvolutionLast.tensor_size
        print("ConvolutionLast", t_size)

        self.add_module("AveragePool", torch.nn.AvgPool2d(t_size[2:]))
        print("AveragePool", (1, 1280, 1, 1))
        self.tensor_size = (1, 1280)

        if n_embedding is not None and n_embedding > 0:
            self.add_module("Embedding", Linear(self.tensor_size, n_embedding,
                                                "", 0., False))
            self.tensor_size = (1, n_embedding)
            print("Linear", (1, n_embedding))


# from core.NeuralLayers import Convolution, ResidualInverted, Linear
# tensor_size = (1, 3, 224, 224)
# tensor = torch.rand(*tensor_size)
# test = MobileNetV2(tensor_size, n_embedding=64)
# test(tensor).size()
