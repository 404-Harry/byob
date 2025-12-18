import argparse
from buildyourownbotnet import create_app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5000, help='Port to run the app on')
    args = parser.parse_args()
    
    app = create_app(test=False)
    app.run(host='0.0.0.0', port=args.port)
