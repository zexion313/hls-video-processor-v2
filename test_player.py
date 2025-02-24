import os
from pathlib import Path
import http.server
import socketserver
import webbrowser
import urllib.parse
from threading import Thread
import requests
from config import LEASEWEB_CONFIG
from storage_handler import LeasewebStorageHandler

class VideoProxyHandler(http.server.SimpleHTTPRequestHandler):
    storage_handler = None  # Will be set when server starts

    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'public, max-age=3600')  # Cache for 1 hour
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/proxy/'):
            # Extract the original path and generate presigned URL
            original_path = self.path.replace('/proxy/', '', 1)
            video_path = urllib.parse.unquote(original_path)
            
            try:
                # Generate presigned URL
                presigned_url = self.storage_handler.generate_presigned_url(video_path)
                
                if not presigned_url:
                    self.send_error(404, "File not found")
                    return

                # Fetch content from storage with increased timeout
                response = requests.get(presigned_url, timeout=30)
                
                if response.status_code == 200:
                    content = response.content
                    
                    # If this is an m3u8 file, modify the URLs
                    if video_path.endswith('.m3u8'):
                        content = self.modify_m3u8_urls(content.decode('utf-8'))
                        content = content.encode('utf-8')
                    
                    # Send response
                    self.send_response(200)
                    self.send_header('Content-Type', self.get_content_type(video_path))
                    self.send_header('Content-Length', len(content))
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    print(f"Storage returned status code: {response.status_code}")
                    self.send_error(response.status_code)
            except requests.Timeout:
                print(f"Timeout while fetching: {video_path}")
                self.send_error(504, "Gateway Timeout")
            except Exception as e:
                print(f"Proxy error for {video_path}: {str(e)}")
                self.send_error(500, str(e))
        else:
            # Serve local files
            super().do_GET()

    def get_content_type(self, path):
        if path.endswith('.m3u8'):
            return 'application/vnd.apple.mpegurl'
        elif path.endswith('.ts'):
            return 'video/mp2t'
        elif path.endswith('.key'):
            return 'application/octet-stream'
        else:
            return 'application/octet-stream'

    def modify_m3u8_urls(self, content):
        """Modify URLs in m3u8 file to use our proxy"""
        lines = content.split('\n')
        modified_lines = []
        
        for line in lines:
            line = line.strip()
            if line.endswith('.ts') or line.endswith('.m3u8') or line.endswith('.key'):
                # Convert the segment path to our proxy URL
                if not line.startswith('http'):
                    if line.startswith('segments/'):
                        # For segment files, add video parameter
                        modified_lines.append(f'/proxy/{line}?video={self.video_name}')
                    else:
                        modified_lines.append(f'/proxy/{line}')
                else:
                    modified_lines.append(line)
            else:
                modified_lines.append(line)
        
        return '\n'.join(modified_lines)

class VideoPlayerTester:
    def __init__(self, storage_handler: LeasewebStorageHandler):
        self.storage = storage_handler
        self.server = None
        self.server_thread = None

    def generate_test_player(self, video_name: str) -> str:
        """Generate a test player HTML file for a specific video"""
        base_path = f"videos/{video_name}"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Player - {video_name}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.4.10/hls.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #f0f0f0;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .video-container {{
            margin-top: 20px;
            margin-bottom: 20px;
        }}
        .info-section {{
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .error-log {{
            background: #fff3f3;
            padding: 10px;
            margin-top: 10px;
            border-radius: 4px;
            display: none;
        }}
        #videoElement {{
            width: 100%;
            max-width: 1000px;
            margin: 0 auto;
        }}
        .status {{
            margin-top: 10px;
            padding: 10px;
            background: #e8f5e9;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Video Test Player - {video_name}</h1>
        
        <div class="video-container">
            <video id="videoElement" controls></video>
        </div>

        <div class="status" id="status">
            Status: Initializing player...
        </div>

        <div class="error-log" id="errorLog">
            <h3>Error Log:</h3>
            <pre id="errorContent"></pre>
        </div>

        <div class="info-section">
            <h2>Video Information</h2>
            <p><strong>Video Name:</strong> {video_name}</p>
            <p><strong>Stream Type:</strong> HLS (HTTP Live Streaming)</p>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const video = document.getElementById('videoElement');
            const errorLog = document.getElementById('errorLog');
            const errorContent = document.getElementById('errorContent');
            const status = document.getElementById('status');
            
            function showError(message) {{
                errorLog.style.display = 'block';
                errorContent.textContent = message;
                console.error(message);
            }}

            function updateStatus(message) {{
                status.textContent = 'Status: ' + message;
                console.log(message);
            }}

            let hls = null;

            function initPlayer() {{
                if (hls) {{
                    hls.destroy();
                    hls = null;
                }}

                if (!window.Hls) {{
                    showError('HLS.js failed to load. Please check your internet connection.');
                    return;
                }}

                if (!Hls.isSupported()) {{
                    updateStatus('HLS not supported in this browser');
                    showError('Your browser does not support HLS playback');
                    return;
                }}

                updateStatus('HLS supported, creating player...');
                
                try {{
                    hls = new Hls({{
                        debug: true,
                        enableWorker: true,
                        maxBufferLength: 30,
                        maxMaxBufferLength: 600,
                        maxBufferSize: 60 * 1000 * 1000,
                        maxBufferHole: 0.5,
                        lowLatencyMode: false,
                        manifestLoadingTimeOut: 20000,
                        manifestLoadingMaxRetry: 4,
                        levelLoadingTimeOut: 20000,
                        levelLoadingMaxRetry: 4,
                        fragLoadingTimeOut: 20000,
                        fragLoadingMaxRetry: 6,
                        startFragPrefetch: true,
                        testBandwidth: true
                    }});

                    hls.on(Hls.Events.MEDIA_ATTACHED, function() {{
                        updateStatus('Media attached, loading manifest...');
                    }});

                    hls.on(Hls.Events.MANIFEST_PARSED, function() {{
                        updateStatus('Manifest loaded, starting playback...');
                        video.play().catch(function(error) {{
                            console.warn('Autoplay prevented:', error);
                            updateStatus('Ready to play (click play button)');
                        }});
                    }});

                    hls.on(Hls.Events.ERROR, function(event, data) {{
                        console.warn('HLS Error:', data);
                        if (data.fatal) {{
                            switch(data.type) {{
                                case Hls.ErrorTypes.NETWORK_ERROR:
                                    updateStatus('Fatal network error, trying to recover...');
                                    hls.startLoad();
                                    break;
                                case Hls.ErrorTypes.MEDIA_ERROR:
                                    updateStatus('Fatal media error, trying to recover...');
                                    hls.recoverMediaError();
                                    break;
                                default:
                                    updateStatus('Fatal error: ' + data.type);
                                    showError('Fatal HLS Error:\\n' + JSON.stringify(data, null, 2));
                                    // Try to reinitialize player
                                    setTimeout(initPlayer, 2000);
                                    break;
                            }}
                        }} else {{
                            updateStatus('Recovered from error: ' + data.type);
                        }}
                    }});

                    // Attach media and load source
                    updateStatus('Attaching media...');
                    hls.attachMedia(video);

                    // Load the source after a small delay to ensure proper initialization
                    setTimeout(() => {{
                        updateStatus('Loading source...');
                        hls.loadSource('/proxy/videos/{video_name}/stream.m3u8');
                    }}, 100);

                    // Add quality level selection
                    hls.on(Hls.Events.LEVEL_LOADED, function(event, data) {{
                        if (data.details) {{
                            updateStatus('Playing - ' + data.details.totalduration.toFixed(1) + 's total duration');
                        }}
                    }});

                    // Monitor buffer state
                    setInterval(function() {{
                        if (video.buffered.length > 0) {{
                            const bufferedEnd = video.buffered.end(video.buffered.length - 1);
                            const duration = video.duration;
                            const bufferedPercent = (bufferedEnd / duration * 100).toFixed(1);
                            console.log('Buffer: ' + bufferedPercent + '%');
                        }}
                    }}, 3000);

                }} catch (error) {{
                    showError('Error initializing player: ' + error.message);
                }}
            }}

            // Monitor video state
            video.addEventListener('playing', function() {{
                updateStatus('Playing');
            }});

            video.addEventListener('waiting', function() {{
                updateStatus('Buffering...');
            }});

            video.addEventListener('error', function(e) {{
                updateStatus('Video error!');
                showError('Video Error: ' + (e.target.error ? e.target.error.message : 'Unknown error'));
            }});

            // Initialize the player
            initPlayer();
        }});
    </script>
</body>
</html>
        """
        
        # Create test_players directory if it doesn't exist
        output_dir = Path("test_players")
        output_dir.mkdir(exist_ok=True)
        
        # Save the HTML file
        output_file = output_dir / f"{video_name}_player.html"
        output_file.write_text(html_content)
        
        return output_file

    def start_server(self, port=8000):
        """Start a local HTTP server"""
        os.chdir(Path("test_players"))  # Change to the test_players directory
        
        # Set the storage handler in the request handler class
        VideoProxyHandler.storage_handler = self.storage
        
        self.server = socketserver.TCPServer(("", port), VideoProxyHandler)
        
        print(f"\n✓ Starting local server at http://localhost:{port}")
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        return port

    def stop_server(self):
        """Stop the local HTTP server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()

def main():
    print("=== Video Player Test Generator ===")
    
    # Initialize storage handler
    storage = LeasewebStorageHandler(LEASEWEB_CONFIG)
    
    # Check storage connection
    if not storage.check_connection():
        print("❌ Failed to connect to storage. Please check your credentials.")
        return
    
    # Initialize player tester
    tester = VideoPlayerTester(storage)
    
    try:
        # Get list of videos in storage
        print("\nGenerating test players...")
        
        # For now, we'll ask the user for the video name
        video_name = input("\nEnter the video name to test (without extension): ").strip()
        
        if not video_name:
            print("❌ No video name provided.")
            return
        
        # Generate test player
        output_file = tester.generate_test_player(video_name)
        
        if output_file and output_file.exists():
            print(f"\n✓ Test player generated successfully!")
            
            # Start local server
            port = tester.start_server()
            
            # Open browser
            player_url = f"http://localhost:{port}/{video_name}_player.html"
            print(f"\nOpening player in your browser: {player_url}")
            webbrowser.open(player_url)
            
            print("\nPress Ctrl+C to stop the server and exit...")
            
            # Keep the main thread running
            while True:
                input()
        else:
            print(f"\n❌ Failed to generate test player for {video_name}")
            print("Please check if the video exists in storage and try again.")

    except KeyboardInterrupt:
        print("\n\nStopping server...")
        tester.stop_server()
        print("Server stopped.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n\n❌ An unexpected error occurred: {str(e)}")
    finally:
        print("\nDone!") 