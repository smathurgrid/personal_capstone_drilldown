"""Service factory dependency injection tests."""

from backend.core.factory import ServiceFactory, reset_service_factory


def test_factory_returns_same_lazy_singleton_per_service() -> None:
    reset_service_factory()
    factory = ServiceFactory()
    first = factory.create_image_generator()
    second = factory.create_image_generator()
    assert first is second


def test_factory_reset_creates_new_instances() -> None:
    reset_service_factory()
    factory = ServiceFactory()
    first = factory.create_history_repository()
    reset_service_factory()
    second = ServiceFactory().create_history_repository()
    assert first is not second


def test_factory_creates_pollinations_image_generator() -> None:
    from backend.shared.config import settings
    from backend.services.explainer.image_generator import PollinationsImageGenerator
    reset_service_factory()
    
    # Save original provider and switch to pollinations
    orig = settings.MODEL_PROVIDER
    settings.MODEL_PROVIDER = "pollinations"
    try:
        factory = ServiceFactory(settings)
        generator = factory.create_image_generator()
        assert isinstance(generator, PollinationsImageGenerator)
    finally:
        settings.MODEL_PROVIDER = orig


def test_pollinations_image_generator_generate() -> None:
    from unittest.mock import MagicMock, patch
    from backend.services.explainer.image_generator import PollinationsImageGenerator
    import asyncio

    generator = PollinationsImageGenerator()
    mock_resp = MagicMock()
    mock_resp.content = b"fake_binary_image_data"
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        res = asyncio.run(generator.generate("test prompt", None, None))
        mock_get.assert_called_once()
        assert "image_b64" in res
        assert len(res["image_b64"]) > 0
        # Verify base64 of b"fake_binary_image_data" is in the output
        import base64
        assert res["image_b64"] == base64.b64encode(b"fake_binary_image_data").decode("utf-8")


def test_factory_creates_fal_image_generator() -> None:
    from backend.shared.config import settings
    from backend.services.explainer.image_generator import FalImageGenerator
    reset_service_factory()
    
    orig = settings.MODEL_PROVIDER
    settings.MODEL_PROVIDER = "fal"
    try:
        factory = ServiceFactory(settings)
        generator = factory.create_image_generator()
        assert isinstance(generator, FalImageGenerator)
    finally:
        settings.MODEL_PROVIDER = orig


def test_fal_image_generator_generate_pov() -> None:
    from unittest.mock import MagicMock, patch
    from backend.services.explainer.image_generator import FalImageGenerator
    import asyncio

    generator = FalImageGenerator()
    
    mock_post_resp = MagicMock()
    mock_post_resp.json = MagicMock(return_value={"images": [{"url": "http://fake.url/image.png"}]})
    mock_post_resp.raise_for_status = MagicMock()

    mock_get_resp = MagicMock()
    mock_get_resp.content = b"fake_fal_image_data"
    mock_get_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_post_resp) as mock_post, \
         patch("requests.get", return_value=mock_get_resp) as mock_get:
         
        res = asyncio.run(generator.generate("first-person view from tower", None, None))
        
        # Verify POST payload contained the POV LoRA and trigger word
        mock_post.assert_called_once()
        post_kwargs = mock_post.call_args[1]
        assert "Key " in post_kwargs["headers"]["Authorization"]
        payload = post_kwargs["json"]
        assert "PVSHTS_PPLSNSM" in payload["prompt"]
        assert len(payload["loras"]) == 1
        assert payload["loras"][0]["scale"] == 0.9

        # Verify it downloaded the image
        mock_get.assert_called_once_with("http://fake.url/image.png", timeout=60)
        
        # Verify response matches
        import base64
        assert res["image_b64"] == base64.b64encode(b"fake_fal_image_data").decode("utf-8")


def test_factory_creates_huggingface_image_generator() -> None:
    from backend.shared.config import settings
    from backend.services.explainer.image_generator import HuggingFaceImageGenerator
    reset_service_factory()
    
    orig = settings.MODEL_PROVIDER
    settings.MODEL_PROVIDER = "huggingface"
    try:
        factory = ServiceFactory(settings)
        generator = factory.create_image_generator()
        assert isinstance(generator, HuggingFaceImageGenerator)
    finally:
        settings.MODEL_PROVIDER = orig


def test_huggingface_image_generator_generate_pov() -> None:
    from unittest.mock import MagicMock, patch
    from backend.services.explainer.image_generator import HuggingFaceImageGenerator
    import asyncio

    generator = HuggingFaceImageGenerator()
    
    mock_post_resp = MagicMock()
    mock_post_resp.content = b"fake_hf_image_bytes"
    mock_post_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_post_resp) as mock_post:
        res = asyncio.run(generator.generate("first-person view from tower", None, None))
        
        # Verify POST payload and headers
        mock_post.assert_called_once()
        post_kwargs = mock_post.call_args[1]
        assert "Bearer " in post_kwargs["headers"]["Authorization"]
        payload = post_kwargs["json"]
        assert "first-person view from tower" in payload["inputs"]

        # Verify response matches base64 of mock_post_resp.content
        import base64
        assert res["image_b64"] == base64.b64encode(b"fake_hf_image_bytes").decode("utf-8")
