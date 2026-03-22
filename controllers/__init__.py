from .audio import FalAudioController
from .base import FalController
from .generate_3d import FalGenerate3DController
from .material import FalMaterialController
from .neural_render import FalNeuralRenderController
from .upscale import FalUpscaleController
from .video import FalDepthVideoController, FalVideoController

__all__ = [
    "FalController",
    "FalAudioController",
    "FalDepthVideoController",
    "FalGenerate3DController",
    "FalMaterialController",
    "FalNeuralRenderController",
    "FalUpscaleController",
    "FalVideoController",
]
