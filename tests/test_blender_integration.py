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
        "FAL_OT_fal_neural_render_operator",
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


def test_pointer_property_for_images():
    """Test that PointerProperty works for Image selection."""
    # Create a test image
    test_img = bpy.data.images.new("test_texture", width=64, height=64)
    
    # Check that our property groups can hold image references
    # (This tests the texture selector fix)
    if hasattr(bpy.context.scene, "fal_3d"):
        # Access upscale props through the 3D scene properties
        props = bpy.context.scene.fal_3d
        if hasattr(props, "upscale") and hasattr(props.upscale, "texture"):
            props.upscale.texture = test_img
            assert props.upscale.texture == test_img, "PointerProperty assignment failed"
            print("✓ PointerProperty for images works")
        else:
            print("⚠ upscale.texture property not found")
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
