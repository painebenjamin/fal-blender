"""
Integration tests that run inside Blender.
Run with: blender --background --python tests/test_blender_integration.py

These tests verify that operators register correctly and basic functionality works.
"""

import sys
import traceback

# Check if we're running in Blender
try:
    import bpy
except ImportError:
    print("ERROR: This test must be run inside Blender")
    print("Usage: blender --background --python tests/test_blender_integration.py")
    sys.exit(1)


def _ensure_extension_enabled():
    """Try to enable the fal.ai extension if not already loaded."""
    if hasattr(bpy.types.Scene, "fal_3d"):
        return True  # Already loaded
    
    from pathlib import Path

    # Get Blender's user extension path via official API
    user_extensions = Path(bpy.utils.user_resource('EXTENSIONS')) / "user_default"
    fal_path = user_extensions / "fal_ai"
    
    if fal_path.exists() and str(user_extensions) not in sys.path:
        sys.path.insert(0, str(user_extensions))
        print(f"Added extension path: {user_extensions}")
    
    # Try addon_utils — this calls register() automatically
    try:
        import addon_utils
        addon_utils.enable('fal_ai', default_set=True)
    except Exception as e:
        print(f"addon_utils.enable failed: {e}")
    
    # Check if it worked
    if hasattr(bpy.types.Scene, "fal_3d"):
        print("fal.ai extension enabled")
        return True
    
    return False


def test_extension_registers():
    """Test that the extension registers without errors."""
    if not _ensure_extension_enabled():
        print("⚠ Skipping: extension not installed or couldn't be enabled")
        print("  Install via: Edit > Preferences > Get Extensions")
        return
    
    # Verify scene property groups
    assert hasattr(bpy.types.Scene, "fal_3d"), \
        "3D scene property group not registered"
    assert hasattr(bpy.types.Scene, "fal_vse"), \
        "VSE scene property group not registered"
    print("✓ Extension property groups registered")


def test_operators_registered():
    """Test that operators are registered."""
    # Extension must be registered first (test_extension_registers runs first)
    if not hasattr(bpy.types.Scene, "fal_3d"):
        print("⚠ Skipping operator test (extension not loaded)")
        return
    
    # Check that our operators exist
    operators = [
        "FAL_OT_fal_render_operator",
        "FAL_OT_fal_video_operator",
        "FAL_OT_fal_upscale_operator",
    ]
    
    for op_name in operators:
        assert hasattr(bpy.types, op_name), f"Operator {op_name} not registered"
    print("✓ Operators registered")


def test_scene_resolution_reading():
    """Test that we can read scene resolution correctly."""
    scene = bpy.context.scene
    
    # Set known values
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 50
    
    # Calculate expected
    scale = scene.render.resolution_percentage / 100.0
    expected_w = int(scene.render.resolution_x * scale)
    expected_h = int(scene.render.resolution_y * scale)
    
    assert expected_w == 960, f"Expected width 960, got {expected_w}"
    assert expected_h == 540, f"Expected height 540, got {expected_h}"
    print("✓ Scene resolution reading works")


def test_render_result_has_data_attribute():
    """Test that Image.has_data exists (Blender 5 compatibility)."""
    # Create a test image
    img = bpy.data.images.new("test_image", width=64, height=64)
    
    # Check has_data attribute exists
    assert hasattr(img, "has_data"), "Image.has_data attribute not found"
    
    # A new image should have data
    assert img.has_data, "New image should have data"
    
    # Cleanup
    bpy.data.images.remove(img)
    print("✓ Image.has_data attribute works")


def test_media_type_for_video_output():
    """Test Blender 5 video output settings."""
    scene = bpy.context.scene
    
    # Check if media_type exists (Blender 5+)
    if hasattr(scene.render.image_settings, "media_type"):
        scene.render.image_settings.media_type = "VIDEO"
        assert scene.render.image_settings.media_type == "VIDEO"
        print("✓ Blender 5 media_type works")
    else:
        # Blender 4.x fallback
        scene.render.image_settings.file_format = "FFMPEG"
        assert scene.render.image_settings.file_format == "FFMPEG"
        print("✓ Blender 4 FFMPEG file_format works")


def test_video_operators_opt_into_confirm():
    """FalVideoOperator always confirms; FalRenderOperator only for VIDEO."""
    if not hasattr(bpy.types.Scene, "fal_3d"):
        print("⚠ Skipping confirm opt-in test (extension not loaded)")
        return

    from fal_ai.controllers.video.operator import FalVideoOperator
    from fal_ai.controllers.render.operator import FalRenderOperator

    ctx = bpy.context
    v_props = ctx.scene.falvideocontroller_props
    r_props = ctx.scene.falrendercontroller_props

    v_props.mode = "TEXT"
    assert FalVideoOperator.needs_confirm(ctx, v_props) is True
    v_props.mode = "IMAGE"
    assert FalVideoOperator.needs_confirm(ctx, v_props) is True

    r_props.render_type = "VIDEO"
    assert FalRenderOperator.needs_confirm(ctx, r_props) is True
    r_props.render_type = "IMAGE"
    assert FalRenderOperator.needs_confirm(ctx, r_props) is False

    print("✓ Video operators opt into confirm; image renders skip it")


def test_confirm_message_has_model_and_size():
    """The confirm body should name the model and the request size."""
    if not hasattr(bpy.types.Scene, "fal_3d"):
        print("⚠ Skipping confirm message test (extension not loaded)")
        return

    from fal_ai.controllers.video.operator import FalVideoOperator
    from fal_ai.models import TextToVideoModel

    ctx = bpy.context
    props = ctx.scene.falvideocontroller_props
    props.mode = "TEXT"
    props.prompt = "a cat surfing"
    props.use_scene_duration = False
    props.duration = 7
    props.use_scene_resolution = False
    props.width = 1280
    props.height = 720

    catalog = TextToVideoModel.catalog()
    first_key = next(iter(catalog.keys()))
    props.text_endpoint = first_key

    title = FalVideoOperator.confirm_title(ctx, props)
    message = FalVideoOperator.confirm_message(ctx, props)
    button = FalVideoOperator.confirm_button(ctx, props)

    assert "text-to-video" in title.lower(), f"Unexpected title: {title}"
    assert "7s" in message, f"Duration missing from message: {message}"
    assert "1280x720" in message, f"Dimensions missing from message: {message}"
    assert catalog[first_key].display_name in message, \
        f"Model name missing from message: {message}"
    assert button == "Generate"

    props.mode = "IMAGE"
    assert "image-to-video" in FalVideoOperator.confirm_title(ctx, props).lower()

    print("✓ Confirm message includes model, duration, and dimensions")


def test_invoke_shows_confirm_for_video_and_skips_for_image():
    """Monkey-patch invoke_confirm, verify it fires for video and not for image render."""
    if not hasattr(bpy.types.Scene, "fal_3d"):
        print("⚠ Skipping invoke_confirm routing test (extension not loaded)")
        return

    captured: list[dict] = []
    original = bpy.types.WindowManager.invoke_confirm

    def fake_invoke_confirm(self, operator, event, **kwargs):
        captured.append({"operator": operator.bl_idname, **kwargs})
        return {"RUNNING_MODAL"}

    try:
        bpy.types.WindowManager.invoke_confirm = fake_invoke_confirm
    except (AttributeError, TypeError) as e:
        print(f"⚠ Skipping: cannot monkey-patch invoke_confirm ({e})")
        return

    try:
        # Video (T2V) — should trigger confirm.
        v_props = bpy.context.scene.falvideocontroller_props
        v_props.mode = "TEXT"
        v_props.prompt = "test prompt"
        bpy.ops.fal.fal_video_operator("INVOKE_DEFAULT")

        video_calls = [c for c in captured if c["operator"] == "fal.fal_video_operator"]
        assert len(video_calls) == 1, \
            f"Expected 1 confirm for video, got {len(video_calls)}: {captured}"
        kwargs = video_calls[0]
        assert "title" in kwargs and kwargs["title"], "confirm title missing"
        assert "message" in kwargs and kwargs["message"], "confirm message missing"
        assert kwargs.get("confirm_text") == "Generate"

        # Image render — confirm must NOT fire.
        r_props = bpy.context.scene.falrendercontroller_props
        r_props.render_type = "IMAGE"
        r_props.mode = "DEPTH"
        r_props.prompt = "test prompt"

        if bpy.context.scene.camera is None:
            cam_data = bpy.data.cameras.new("TestCamera")
            cam = bpy.data.objects.new("TestCamera", cam_data)
            bpy.context.scene.collection.objects.link(cam)
            bpy.context.scene.camera = cam

        before = len(captured)
        # Image render actually starts a real render — we only care that the
        # dialog does NOT fire. Wrap in try to swallow downstream errors.
        try:
            bpy.ops.fal.fal_render_operator("INVOKE_DEFAULT")
        except Exception:
            pass
        image_calls = [
            c for c in captured[before:]
            if c["operator"] == "fal.fal_render_operator"
        ]
        assert len(image_calls) == 0, \
            f"Image render should not confirm, got: {image_calls}"

        print("✓ Confirm fires for video, skipped for image render")
    finally:
        bpy.types.WindowManager.invoke_confirm = original
        # Cancel any render that may have started.
        try:
            from fal_ai.controllers.render.operator import FalRenderOperator
            FalRenderOperator._rendering = False
        except Exception:
            pass


def test_pointer_property_for_images():
    """Test that PointerProperty works for Image selection."""
    # Create a test image
    test_img = bpy.data.images.new("test_texture", width=64, height=64)
    
    # Check that our property groups can hold image references
    # (This tests the texture selector fix)
    # Controller props are registered as {controllername}_props
    props_name = "falupscalecontroller_props"
    if hasattr(bpy.context.scene, props_name):
        props = getattr(bpy.context.scene, props_name)
        if hasattr(props, "texture"):
            props.texture = test_img
            assert props.texture == test_img, "PointerProperty assignment failed"
            print("✓ PointerProperty for images works")
        else:
            print("⚠ texture property not found on upscale props")
    else:
        print("⚠ Skipping PointerProperty test (extension not loaded)")
    
    # Cleanup
    bpy.data.images.remove(test_img)


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_extension_registers,
        test_operators_registered,
        test_scene_resolution_reading,
        test_render_result_has_data_attribute,
        test_media_type_for_video_output,
        test_video_operators_opt_into_confirm,
        test_confirm_message_has_model_and_size,
        test_invoke_shows_confirm_for_video_and_skips_for_image,
        test_pointer_property_for_images,
    ]
    
    passed = 0
    failed = 0
    
    print("\n" + "=" * 60)
    print("fal.ai Blender Extension - Integration Tests")
    print("=" * 60 + "\n")
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error")
            traceback.print_exc()
            failed += 1
    
    print("\n" + "-" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("-" * 60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
