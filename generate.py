import os
import sys
import secrets
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Optional
from config import LEASEWEB_CONTROL_CONFIG, LEASEWEB_CDN_CONFIG, INPUT_DIR, OUTPUT_DIR, FFMPEG_PATH, SEGMENT_DURATION, KEY_LENGTH
from storage_handler import LeasewebStorageHandler

class VideoProcessor:
    def __init__(self, input_dir: str, output_dir: str, storage_handler: LeasewebStorageHandler):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.storage = storage_handler

    def test_storage_connection(self) -> bool:
        """Test connection to storage and basic operations"""
        print("\n=== Testing Storage Connection ===")
        
        # 1. Test basic connection
        if not self.storage.check_connection():
            print("❌ Basic connection test failed!")
            return False
        print("✓ Basic connection test passed!")

        # 2. Test presigned URL generation
        print("\nTesting presigned URL generation...")
        test_url = self.storage.generate_presigned_url("test.txt")
        if not test_url:
            print("❌ Presigned URL generation test failed!")
            return False
        print("✓ Presigned URL generation test passed!")
        print(f"Sample presigned URL: {test_url}")

        print("\n✓ All storage tests passed successfully!")
        return True

    def validate_environment(self) -> bool:
        """Validate all required components"""
        print("\n=== Validating Environment ===")
        
        # 1. Check FFmpeg
        if not os.path.exists(FFMPEG_PATH):
            print("❌ FFmpeg not found at:", FFMPEG_PATH)
            return False
        print("✓ FFmpeg found!")

        # 2. Check input directory
        if not self.input_dir.exists():
            print(f"Creating input directory at {self.input_dir}")
            self.input_dir.mkdir(parents=True, exist_ok=True)
        print("✓ Input directory ready!")

        # 3. Check output directory
        if not self.output_dir.exists():
            print(f"Creating output directory at {self.output_dir}")
            self.output_dir.mkdir(parents=True, exist_ok=True)
        print("✓ Output directory ready!")

        return True

    def _generate_key(self) -> tuple[bytes, str]:
        """Generate encryption key and key URL."""
        key = secrets.token_bytes(KEY_LENGTH)
        return key, "key.key"

    def _setup_video_directory(self, video_name: str) -> Dict[str, Path]:
        """Create output directory structure for a video."""
        video_dir = self.output_dir / video_name
        segments_dir = video_dir / "segments"
        
        # Clean up any existing directory
        if video_dir.exists():
            shutil.rmtree(video_dir)
        
        # Create directories
        segments_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "video_dir": video_dir,
            "segments_dir": segments_dir
        }

    def _write_key_file(self, video_dir: Path, key: bytes, key_url: str):
        """Write encryption key and key info file."""
        # Write key file
        with open(video_dir / "key.key", "wb") as f:
            f.write(key)

        # Write key info file
        with open(video_dir / "key_info", "w") as f:
            f.write(f"{key_url}\n{str(video_dir / 'key.key')}\n")

    def _create_iframe_playlist(self, input_file: Path, video_dir: Path):
        """Create iframe playlist without generating segments."""
        temp_dir = video_dir / "temp_iframes"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Generate temporary iframe playlist
            iframe_cmd = [
                FFMPEG_PATH,
                "-i", str(input_file),
                "-map", "0:v",
                "-c:v", "copy",
                "-f", "hls",
                "-hls_time", str(SEGMENT_DURATION),
                "-hls_playlist_type", "vod",
                "-hls_flags", "independent_segments+iframes_only",
                "-hls_segment_type", "fmp4",
                "-hls_list_size", "0",
                str(temp_dir / "iframes.m3u8")
            ]
            
            subprocess.run(iframe_cmd, check=True, capture_output=True, text=True)
            
            # Move only the m3u8 file
            shutil.move(str(temp_dir / "iframes.m3u8"), str(video_dir / "iframes.m3u8"))
            
        finally:
            # Clean up temporary directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def process_video(self, input_file: Path) -> bool:
        """Process a single video file and upload to storage."""
        video_name = input_file.stem
        print(f"\n=== Processing video: {video_name} ===")

        # Setup directories
        dirs = self._setup_video_directory(video_name)
        video_dir = dirs["video_dir"]
        segments_dir = dirs["segments_dir"]

        try:
            # Generate encryption key
            key, key_url = self._generate_key()
            self._write_key_file(video_dir, key, key_url)

            # Generate main stream playlist
            print("1. Generating main stream playlist...")
            stream_cmd = [
                FFMPEG_PATH,
                "-i", str(input_file),
                "-hls_time", str(SEGMENT_DURATION),
                "-hls_key_info_file", str(video_dir / "key_info"),
                "-hls_playlist_type", "vod",
                "-hls_segment_filename", str(segments_dir / "segment_%03d.ts"),
                "-hls_flags", "independent_segments",
                "-hls_list_size", "0",
                "-hls_base_url", "segments/",
                "-c", "copy",
                str(video_dir / "stream.m3u8")
            ]
            subprocess.run(stream_cmd, check=True, capture_output=True, text=True)
            print("✓ Main stream playlist generated!")
            
            # Generate iframe playlist
            print("2. Generating iframe playlist...")
            self._create_iframe_playlist(input_file, video_dir)
            print("✓ Iframe playlist generated!")

            # Upload to storage
            print("3. Uploading to storage...")
            if self.storage.upload_video_files(video_name, video_dir):
                print("✓ Successfully uploaded all files!")
                # Clean up local files after successful upload
                shutil.rmtree(video_dir)
                return True
            return False

        except subprocess.CalledProcessError as e:
            print(f"❌ Error processing {video_name}: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ Error processing {video_name}: {str(e)}")
            return False

    def process_all_videos(self) -> bool:
        """Process all MP4 files in the input directory."""
        mp4_files = list(self.input_dir.glob("*.mp4"))
        
        if not mp4_files:
            print("\n❌ No MP4 files found in input directory.")
            print(f"Please place MP4 files in: {self.input_dir}")
            return False

        print(f"\nFound {len(mp4_files)} MP4 files to process.")
        
        successful = 0
        for input_file in mp4_files:
            if self.process_video(input_file):
                successful += 1

        print(f"\n=== Processing Summary ===")
        print(f"Total videos: {len(mp4_files)}")
        print(f"Successfully processed: {successful}")
        print(f"Failed: {len(mp4_files) - successful}")
        
        return successful == len(mp4_files)

def main():
    print("=== Video Processing System ===")
    
    # Initialize storage handler with both configurations
    storage = LeasewebStorageHandler(
        control_config=LEASEWEB_CONTROL_CONFIG,
        cdn_config=LEASEWEB_CDN_CONFIG
    )
    
    # Initialize video processor
    processor = VideoProcessor(
        input_dir=INPUT_DIR,
        output_dir=OUTPUT_DIR,
        storage_handler=storage
    )

    # Step 1: Validate environment
    if not processor.validate_environment():
        print("\n❌ Environment validation failed. Please fix the issues and try again.")
        return

    # Step 2: Test storage connection
    if not processor.test_storage_connection():
        print("\n❌ Storage connection test failed. Please check your credentials and try again.")
        return

    # Step 3: Process videos
    print("\n=== Starting Video Processing ===")
    processor.process_all_videos()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n\n❌ An unexpected error occurred: {str(e)}")
    finally:
        print("\nDone!")
