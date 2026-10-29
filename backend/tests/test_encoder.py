import numpy as np

from galeria.core.encoder import ClipEncoder, FakeEncoder, l2_normalize, resolve_device


def test_clip_encoder_keeps_text_on_its_own_device_without_loading_models():
    encoder = ClipEncoder("img-model", "txt-model", device="mps", text_device="cpu")
    assert (encoder.device, encoder.text_device) == ("mps", "cpu")
    assert encoder.name == "img-model+txt-model"
    assert encoder._image_model is None and encoder._text_model is None  # still lazy


def test_text_device_defaults_to_cpu():
    assert ClipEncoder("a", "b").text_device == "cpu"
    assert resolve_device("cuda") == "cuda"
    assert resolve_device("auto") in {"cpu", "mps", "cuda"}


def test_fake_encoder_outputs_unit_vectors():
    vectors = FakeEncoder().encode_texts(["red", "anything else", "kırmızı yeşil"])
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert np.allclose(l2_normalize(np.array([[3.0, 4.0]])), [[0.6, 0.8]])
