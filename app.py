from flask import Flask, Response, request, send_from_directory, __version__ as flask_version
import requests
import urllib.parse
import logging
import json
import os
import sys
from flask_cors import CORS
from datetime import datetime

# Configure logging before anything else
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    CORS(app)

    @app.route('/health')
    def health_check():
        """Lightweight health check endpoint"""
        try:
            return {"status": "healthy"}, 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {"status": "unhealthy", "error": str(e)}, 500

    # Add error handlers
    @app.errorhandler(500)
    def handle_500(e):
        logger.error(f"Internal server error: {str(e)}")
        return {"error": "Internal Server Error", "message": str(e)}, 500

    @app.errorhandler(404)
    def handle_404(e):
        return {"error": "Not Found", "message": str(e)}, 404

    @app.errorhandler(502)
    def handle_502(e):
        logger.error(f"Bad Gateway error: {str(e)}")
        return {"error": "Bad Gateway", "message": str(e)}, 502

    @app.route('/')
    def serve_video_library():
        """Serve the video library page"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Video Library</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: #f0f0f0;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                h1 {
                    color: #333;
                    text-align: center;
                    margin-bottom: 30px;
                }
                .video-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 20px;
                    padding: 20px;
                }
                .video-card {
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    transition: transform 0.2s;
                    cursor: pointer;
                }
                .video-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                }
                .video-thumbnail {
                    width: 100%;
                    height: 180px;
                    background: #ddd;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .video-info {
                    padding: 15px;
                }
                .video-title {
                    margin: 0;
                    font-size: 18px;
                    color: #333;
                }
                .search-bar {
                    margin-bottom: 20px;
                    text-align: center;
                }
                .search-bar input {
                    padding: 10px;
                    width: 300px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    margin-right: 10px;
                }
                .loading {
                    text-align: center;
                    padding: 20px;
                    font-size: 18px;
                    color: #666;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Video Library</h1>
                <div class="search-bar">
                    <input type="text" id="searchInput" placeholder="Search videos..." oninput="filterVideos()">
                </div>
                <div id="videoGrid" class="video-grid">
                    <div class="loading">Loading videos...</div>
                </div>
            </div>

            <script>
                // Function to load videos
                async function loadVideos() {
                    try {
                        const response = await fetch('/videos');
                        const videos = await response.json();
                        displayVideos(videos);
                    } catch (error) {
                        console.error('Error loading videos:', error);
                        document.getElementById('videoGrid').innerHTML = 
                            '<div style="color: red; text-align: center;">Error loading videos. Please try again.</div>';
                    }
                }

                // Function to display videos
                function displayVideos(videos) {
                    const grid = document.getElementById('videoGrid');
                    if (videos.length === 0) {
                        grid.innerHTML = '<div style="text-align: center; grid-column: 1/-1;">No videos available</div>';
                        return;
                    }
                    grid.innerHTML = videos.map(video => `
                        <div class="video-card" onclick="playVideo('${video}')">
                            <div class="video-thumbnail">
                                <svg width="64" height="64" viewBox="0 0 24 24" fill="#666">
                                    <path d="M8 5v14l11-7z"/>
                                </svg>
                            </div>
                            <div class="video-info">
                                <h3 class="video-title">${video}</h3>
                            </div>
                        </div>
                    `).join('');
                }

                // Function to filter videos
                function filterVideos() {
                    const search = document.getElementById('searchInput').value.toLowerCase();
                    const cards = document.getElementsByClassName('video-card');
                    
                    for (let card of cards) {
                        const title = card.getElementsByClassName('video-title')[0].textContent.toLowerCase();
                        card.style.display = title.includes(search) ? '' : 'none';
                    }
                }

                // Function to play video
                function playVideo(videoName) {
                    window.location.href = `/player?video=${encodeURIComponent(videoName)}`;
                }

                // Load videos when page loads
                loadVideos();
            </script>
        </body>
        </html>
        """
        return html

    @app.route('/videos')
    def get_videos():
        """Get list of available videos"""
        videos = ['fly', 'song', 'sparkle', 'maverick', 'transformers', 'whiplash']
        return json.dumps(videos)

    @app.route('/player')
    def serve_video_player():
        """Serve the video player page"""
        video_name = request.args.get('video')
        if not video_name:
            return "Video name not specified", 400

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Playing {video_name}</title>
    <!-- Video.js CSS -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/video.js/8.5.3/video-js.min.css" rel="stylesheet">
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
            position: relative;
            width: 100%;
            max-width: 1000px;
            margin: 0 auto;
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
        .status {{
            margin-top: 10px;
            padding: 10px;
            background: #e8f5e9;
            border-radius: 4px;
        }}
        .back-button {{
            display: inline-block;
            padding: 10px 20px;
            background: #4a90e2;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            margin-bottom: 20px;
        }}
        .back-button:hover {{
            background: #357abd;
        }}
        .source-info {{
            margin-top: 10px;
            padding: 15px;
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .note {{
            font-style: italic;
            color: #666;
            margin-top: 10px;
            font-size: 0.9em;
        }}
        code {{
            background: #eee;
            padding: 4px 8px;
            border-radius: 4px;
            font-family: monospace;
            word-break: break-all;
        }}
        /* Custom Video.js theme */
        .video-js {{
            width: 100%;
            height: 0;
            padding-top: 56.25%; /* 16:9 Aspect Ratio */
        }}
        .video-js .vjs-big-play-button {{
            background-color: rgba(74, 144, 226, 0.9);
            border-color: #4a90e2;
        }}
        .video-js .vjs-control-bar {{
            background-color: rgba(43, 51, 63, 0.9);
        }}
        .video-js .vjs-slider {{
            background-color: rgba(255, 255, 255, 0.3);
        }}
        .video-js .vjs-play-progress {{
            background-color: #4a90e2;
        }}
        .video-js .vjs-volume-level {{
            background-color: #4a90e2;
        }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-button">← Back to Library</a>
        <h1>Playing: {video_name}</h1>
        
        <div class="video-container">
            <video id="videoPlayer" 
                   class="video-js vjs-default-skin vjs-big-play-centered"
                   controls
                   preload="auto">
                <source src="/proxy/videos/{video_name}/stream.m3u8" type="application/x-mpegURL">
                <p class="vjs-no-js">
                    To view this video please enable JavaScript, and consider upgrading to a
                    web browser that <a href="https://videojs.com/html5-video-support/" target="_blank">supports HTML5 video</a>
                </p>
            </video>
        </div>

        <div class="status" id="status">
            Status: Initializing player...
        </div>

        <div class="error-log" id="errorLog">
            <h3>Error Log:</h3>
            <pre id="errorContent"></pre>
        </div>

        <div class="info-section">
            <h2>Video Source Information</h2>
            <div class="source-info">
                <p><strong>Video Name:</strong> {video_name}</p>
                <p><strong>Stream Type:</strong> HLS (HTTP Live Streaming)</p>
                <p><strong>CDN Provider:</strong> Leaseweb CDN</p>
                <p><strong>Source URL:</strong><br>
                <code>https://di-yusrkfqf.leasewebultracdn.com/videos/{video_name}/stream.m3u8</code></p>
                <p class="note">This video is served through Leaseweb's Content Delivery Network (CDN) for optimal streaming performance and global availability.</p>
            </div>
        </div>
    </div>

    <!-- Video.js JavaScript -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/video.js/8.5.3/video.min.js"></script>

    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const status = document.getElementById('status');
            const errorLog = document.getElementById('errorLog');
            const errorContent = document.getElementById('errorContent');
            
            function showError(message) {{
                errorLog.style.display = 'block';
                errorContent.textContent = message;
                console.error(message);
            }}

            function updateStatus(message) {{
                status.textContent = 'Status: ' + message;
                console.log(message);
            }}

            // Initialize Video.js player
            const player = videojs('videoPlayer', {{
                fluid: true,
                controls: true,
                autoplay: false,
                preload: 'auto',
                playbackRates: [0.5, 1, 1.5, 2],
                html5: {{
                    vhs: {{
                        overrideNative: true,
                        fastQualityChange: true,
                        useBandwidthFromLocalStorage: true
                    }},
                    nativeAudioTracks: false,
                    nativeVideoTracks: false
                }}
            }});

            // Event handlers
            player.on('ready', function() {{
                updateStatus('Player ready');
                // Force player dimensions after ready
                player.dimensions(player.width(), player.width() * 9/16);
            }});

            player.on('play', function() {{
                updateStatus('Playing');
            }});

            player.on('pause', function() {{
                updateStatus('Paused');
            }});

            player.on('waiting', function() {{
                updateStatus('Buffering...');
            }});

            player.on('error', function(error) {{
                updateStatus('Error occurred');
                showError('Player Error: ' + player.error().message);
            }});

            // Cleanup on page unload
            window.addEventListener('beforeunload', function() {{
                player.dispose();
            }});
        }});
    </script>
</body>
</html>
"""
        return html

    @app.route('/test-cdn/<video_name>')
    def test_cdn(video_name):
        """Test CDN connectivity for a specific video"""
        try:
            # Test m3u8 playlist
            playlist_url = f"https://di-yusrkfqf.leasewebultracdn.com/videos/{video_name}/stream.m3u8"
            logger.info(f"Testing CDN connection to: {playlist_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity'
            }
            
            response = requests.head(playlist_url, headers=headers, timeout=10)
            
            return {
                "status": "success" if response.status_code == 200 else "error",
                "url_tested": playlist_url,
                "status_code": response.status_code,
                "headers": dict(response.headers)
            }
            
        except Exception as e:
            logger.error(f"CDN test failed: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}, 500

    @app.route('/proxy/<path:target_path>')
    def proxy_request(target_path):
        """Handle proxy requests to CDN"""
        try:
            logger.info(f"=== Starting proxy request for: {target_path} ===")

            # Extract video name from the path
            path_parts = target_path.split('/')
            if len(path_parts) >= 2 and path_parts[0] == 'videos':
                video_name = path_parts[1]
                logger.info(f"Extracted video name: {video_name}")
            else:
                logger.error(f"Invalid path format: {target_path}")
                return {"error": "Invalid path", "message": "Could not extract video name"}, 400

            # Construct the CDN URL
            cdn_url = f"https://di-yusrkfqf.leasewebultracdn.com/{target_path}"
            logger.info(f"Requesting from CDN: {cdn_url}")

            try:
                # Set up headers for the CDN request
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': '*/*',
                    'Accept-Encoding': 'identity',  # Request uncompressed content
                    'Connection': 'keep-alive'
                }

                # Make the request to the CDN
                response = requests.get(cdn_url, headers=headers, timeout=30, stream=True)
                logger.info(f"CDN response status: {response.status_code}")
                logger.info(f"CDN response headers: {dict(response.headers)}")

                if response.status_code == 200:
                    content = response.content
                    logger.info(f"Received content length: {len(content)} bytes")

                    # If this is an m3u8 file, modify the URLs
                    if target_path.endswith('.m3u8'):
                        try:
                            decoded_content = content.decode('utf-8')
                            logger.info("=== Original m3u8 content ===")
                            logger.info(decoded_content)
                            logger.info("=== End original m3u8 content ===")
                            
                            # Basic content validation
                            if not decoded_content.strip():
                                logger.error("Empty m3u8 content received")
                                return {"error": "Invalid Content", "message": "Empty m3u8 file received"}, 500

                            # Check for HLS header
                            if not decoded_content.strip().startswith('#EXTM3U'):
                                logger.error("Invalid m3u8 content - missing #EXTM3U header")
                                return {"error": "Invalid Content", "message": "Invalid m3u8 file format"}, 500

                            # Modify URLs
                            content = modify_m3u8_urls(decoded_content, video_name)
                            content = content.encode('utf-8')
                            
                            logger.info("=== Modified m3u8 content ===")
                            logger.info(content.decode('utf-8'))
                            logger.info("=== End modified m3u8 content ===")
                            
                        except UnicodeDecodeError as e:
                            logger.error(f"Failed to decode m3u8 content: {str(e)}")
                            return {"error": "Processing Error", "message": "Failed to decode m3u8 content"}, 500
                        except Exception as e:
                            logger.error(f"Error processing m3u8: {str(e)}", exc_info=True)
                            return {"error": "Processing Error", "message": f"Failed to process m3u8: {str(e)}"}, 500

                    # Determine content type
                    content_type = get_content_type(target_path)
                    logger.info(f"Content-Type determined: {content_type}")

                    # Create response with proper headers
                    flask_response = Response(content)
                    flask_response.headers['Content-Type'] = content_type
                    flask_response.headers['Content-Length'] = len(content)
                    flask_response.headers['Access-Control-Allow-Origin'] = '*'
                    flask_response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
                    flask_response.headers['Access-Control-Allow-Headers'] = '*'
                    flask_response.headers['Cache-Control'] = 'public, max-age=3600'
                    
                    logger.info("=== Response headers ===")
                    logger.info(dict(flask_response.headers))
                    logger.info("=== End response headers ===")
                    
                    return flask_response
                    
                elif response.status_code == 501:
                    logger.error("CDN returned 501 Not Implemented - retrying without compression")
                    # Retry without any encoding
                    headers['Accept-Encoding'] = 'identity'
                    response = requests.get(cdn_url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        return handle_cdn_response(response, target_path, video_name)
                    else:
                        error_msg = f"CDN retry failed with status {response.status_code}"
                        logger.error(error_msg)
                        return {"error": "CDN Error", "message": error_msg}, response.status_code
                else:
                    error_msg = f"CDN returned status {response.status_code}"
                    if response.content:
                        error_msg += f": {response.content.decode('utf-8', errors='ignore')}"
                    logger.error(error_msg)
                    return {"error": "CDN Error", "message": error_msg}, response.status_code

            except requests.Timeout:
                logger.error(f"Timeout while fetching: {cdn_url}")
                return {"error": "Gateway Timeout", "message": "Request to CDN timed out"}, 504
            except requests.RequestException as e:
                logger.error(f"Request error: {str(e)}")
                return {"error": "CDN Request Failed", "message": str(e)}, 502

        except Exception as e:
            logger.error(f"Proxy error: {str(e)}", exc_info=True)
            return {"error": "Internal Server Error", "message": str(e)}, 500

    def handle_cdn_response(response, target_path, video_name):
        """Helper function to process CDN response"""
        try:
            content = response.content
            logger.info(f"Received content length: {len(content)} bytes")

            if target_path.endswith('.m3u8'):
                try:
                    decoded_content = content.decode('utf-8')
                    logger.info("=== Original m3u8 content ===")
                    logger.info(decoded_content)
                    logger.info("=== End original m3u8 content ===")
                    
                    if not decoded_content.strip():
                        logger.error("Empty m3u8 content received")
                        return {"error": "Invalid Content", "message": "Empty m3u8 file received"}, 500

                    if not decoded_content.strip().startswith('#EXTM3U'):
                        logger.error("Invalid m3u8 content - missing #EXTM3U header")
                        return {"error": "Invalid Content", "message": "Invalid m3u8 file format"}, 500

                    content = modify_m3u8_urls(decoded_content, video_name)
                    content = content.encode('utf-8')
                    
                    logger.info("=== Modified m3u8 content ===")
                    logger.info(content.decode('utf-8'))
                    logger.info("=== End modified m3u8 content ===")
                    
                except UnicodeDecodeError as e:
                    logger.error(f"Failed to decode m3u8 content: {str(e)}")
                    return {"error": "Processing Error", "message": "Failed to decode m3u8 content"}, 500

            content_type = get_content_type(target_path)
            flask_response = Response(content)
            flask_response.headers['Content-Type'] = content_type
            flask_response.headers['Content-Length'] = len(content)
            flask_response.headers['Access-Control-Allow-Origin'] = '*'
            flask_response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            flask_response.headers['Access-Control-Allow-Headers'] = '*'
            flask_response.headers['Cache-Control'] = 'public, max-age=3600'
            
            return flask_response

        except Exception as e:
            logger.error(f"Error handling CDN response: {str(e)}", exc_info=True)
            return {"error": "Processing Error", "message": str(e)}, 500

    def get_content_type(path):
        """Determine content type based on file extension"""
        if path.endswith('.m3u8'):
            return 'application/vnd.apple.mpegurl'
        elif path.endswith('.ts'):
            return 'video/mp2t'
        elif path.endswith('.key'):
            return 'application/octet-stream'
        else:
            return 'application/octet-stream'

    def modify_m3u8_urls(content, video_name=None):
        """Modify URLs in m3u8 file to use our proxy"""
        lines = content.split('\n')
        modified_lines = []
        
        for line in lines:
            line = line.strip()
            if line.endswith('.ts') or line.endswith('.m3u8') or line.endswith('.key'):
                # Convert the segment path to our proxy URL
                if not line.startswith('http'):
                    # If it's a segment file and doesn't have the full path
                    if line.startswith('segments/') or line.endswith('.ts'):
                        modified_lines.append(f'/proxy/videos/{video_name}/{line}')
                    else:
                        modified_lines.append(f'/proxy/videos/{video_name}/{line}')
                else:
                    modified_lines.append(line)
            else:
                modified_lines.append(line)
        
        logger.info(f"Modified m3u8 content:\n{'\n'.join(modified_lines)}")
        return '\n'.join(modified_lines)

    return app

# Create the application instance
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)