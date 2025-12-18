#!/bin/bash
echo "WARNING: This script will install docker AND add it as an apt source."
echo ""
echo "If you do not want this, please press ctrl + C to cancel the script."
echo ""
echo "The script will start in 10 seconds."

sleep 10

echo "Running BYOB multi-server setup..."

# Default values
DB_SERVER_IP="localhost"
ROLE="both"  # db, app, both

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --db-server)
      DB_SERVER_IP="$2"
      shift 2
      ;;
    --role)
      ROLE="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--db-server IP] [--role db|app|both]"
      exit 1
      ;;
  esac
done

# Validate arguments
if [[ "$ROLE" == "app" && "$DB_SERVER_IP" == "localhost" ]]; then
  echo "Error: --db-server must be specified when using --role app"
  exit 1
fi

echo "DB Server IP: $DB_SERVER_IP"
echo "Role: $ROLE"

# Install Python if necessary
which python3 > /dev/null
status=$?

if test $status -ne 0
then
	echo "Installing Python 3.6..."
	sudo apt-get update
	apt-get install python3.6 -y
else
	echo "Confirmed Python is installed."
fi

# Install pip if not present
which pip3 > /dev/null
if test $? -ne 0
then
	echo "Installing pip..."
	sudo apt install python3-pip -y
fi

# Install PostgreSQL if necessary and role includes db
if [[ "$ROLE" == "db" || "$ROLE" == "both" ]]; then
	which psql > /dev/null
	status=$?

	if test $status -ne 0
	then
		echo "Installing PostgreSQL..."
		sudo apt-get install postgresql postgresql-contrib -y
		sudo systemctl start postgresql
		sudo systemctl enable postgresql
	fi

	# Get PostgreSQL version
	PG_VERSION=$(ls /etc/postgresql/ | head -1)
	if [ -z "$PG_VERSION" ]; then
		echo "Error: Could not determine PostgreSQL version"
		exit 1
	fi
	echo "PostgreSQL version: $PG_VERSION"

	# Check if user exists
	sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='byob_user'" | grep -q 1
	if [ $? -ne 0 ]; then
		echo "Creating database user..."
		sudo -u postgres createuser --createdb byob_user
		sudo -u postgres psql -c "ALTER USER byob_user PASSWORD 'byob_password';"
	else
		echo "Database user already exists."
	fi

	# Check if DB exists
	sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw byob_db
	if [ $? -ne 0 ]; then
		echo "Creating database..."
		sudo -u postgres createdb -O byob_user byob_db
	else
		echo "Database already exists."
	fi

	# Configure for remote access
	PG_CONF="/etc/postgresql/$PG_VERSION/main/postgresql.conf"
	PG_HBA="/etc/postgresql/$PG_VERSION/main/pg_hba.conf"
	sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" "$PG_CONF"
	grep -q "host    byob_db     byob_user" "$PG_HBA"
	if [ $? -ne 0 ]; then
		echo "host    byob_db     byob_user     0.0.0.0/0     md5" | sudo tee -a "$PG_HBA"
	fi
	sudo systemctl restart postgresql

	echo "PostgreSQL configured. URI: postgresql://byob_user:byob_password@$DB_SERVER_IP/byob_db"
else
	echo "Skipping PostgreSQL setup (role: $ROLE)"
fi

# Install Nginx for load balancing if role includes app
if [[ "$ROLE" == "app" || "$ROLE" == "both" ]]; then
	which nginx > /dev/null
	status=$?

	if test $status -ne 0
	then
		echo "Installing Nginx..."
		sudo apt-get install nginx -y
		sudo systemctl start nginx
		sudo systemctl enable nginx
	else
		echo "Confirmed Nginx is installed."
	fi
else
	echo "Skipping Nginx setup (role: $ROLE)"
fi

# Install Docker if necessary
which docker > /dev/null
status=$?

if test $status -ne 0
then
	echo "Installing Docker..."
	chmod +x get-docker.sh
	./get-docker.sh
	sudo usermod -aG docker $USER
	sudo chmod 666 /var/run/docker.sock
else
	echo "Confirmed Docker is installed."
	echo "If you run into issues generating a Windows payload, please uninstall docker and rerun this script"
fi

# Install Docker Compose if not present
which docker-compose > /dev/null
if test $? -ne 0
then
	echo "Installing Docker Compose..."
	sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
	sudo chmod +x /usr/local/bin/docker-compose
else
	echo "Confirmed Docker Compose is installed."
fi

# Install Python packages
echo "Installing Python packages..."
python3 -m pip install --upgrade pip
python3 -m pip install CMake==3.18.4
python3 -m pip install -r requirements.txt

# Set environment variable for database
if [[ "$ROLE" == "db" || "$ROLE" == "both" ]]; then
	export SQLALCHEMY_DATABASE_URI="postgresql://byob_user:byob_password@localhost/byob_db"
else
	export SQLALCHEMY_DATABASE_URI="postgresql://byob_user:byob_password@$DB_SERVER_IP/byob_db"
fi
echo "Database URI set to: $SQLALCHEMY_DATABASE_URI"

# Save to .env file for persistence
echo "SQLALCHEMY_DATABASE_URI=$SQLALCHEMY_DATABASE_URI" > .env
echo "Environment saved to .env file"

# Configure Nginx if app role
if [[ "$ROLE" == "app" || "$ROLE" == "both" ]]; then
	if [ ! -f /etc/nginx/sites-available/byob ]; then
		sudo cp byob_nginx.conf /etc/nginx/sites-available/byob
		sudo ln -s /etc/nginx/sites-available/byob /etc/nginx/sites-enabled/ 2>/dev/null || true
		sudo nginx -t && sudo systemctl reload nginx
	else
		echo "Nginx config already exists."
	fi
else
	echo "Skipping Nginx configuration (role: $ROLE)"
fi

# Add to hosts for command.lan if app role
if [[ "$ROLE" == "app" || "$ROLE" == "both" ]]; then
	grep -q "command.lan" /etc/hosts
	if [ $? -ne 0 ]; then
		echo "127.0.0.1 command.lan" | sudo tee -a /etc/hosts
	else
		echo "command.lan already in hosts."
	fi
fi

# Build Docker images
echo "Building Docker images - this will take a while, please be patient..."
cd docker-pyinstaller
docker build -f Dockerfile-py3-amd64 -t nix-amd64 .
docker build -f Dockerfile-py3-i386 -t nix-i386 .
docker build -f Dockerfile-py3-win32 -t win-x32 .
cd ..

read -p "To use some Byob features, you must reboot your system. If this is not your first time running this script, please answer no. Reboot now? [Y/n]: " agreeTo
#Reboots system if user answers Yes
case $agreeTo in
    y|Y|yes|Yes|YES)
    echo "Rebooting..."
    sleep 1
    sudo reboot now
    exit
    ;;
#Provides instructions if user answers No
    n|N|no|No|NO)
    echo "Setup complete!"
    if [[ "$ROLE" == "db" || "$ROLE" == "both" ]]; then
        echo "This server is configured as database server."
        echo "Database URI: postgresql://byob_user:byob_password@$DB_SERVER_IP/byob_db"
    fi
    if [[ "$ROLE" == "app" || "$ROLE" == "both" ]]; then
        echo "To start services manually:"
        echo "  source .env"
        echo "  python3 run.py --port 5000 &"
        echo "  python3 run.py --port 5001 &"
        echo "  python3 run.py --port 5002 &"
        echo "  cd ../byob"
        echo "  python3 -m byob.server --database \"$SQLALCHEMY_DATABASE_URI\" --port 1337 &"
        echo "  python3 -m byob.server --database \"$SQLALCHEMY_DATABASE_URI\" --port 1338 &"
        echo ""
        echo "To start with systemd services:"
        echo "  sudo cp byob-web.service /etc/systemd/system/"
        echo "  sudo cp ../byob/byob-c2.service /etc/systemd/system/"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable byob-web"
        echo "  sudo systemctl enable byob-c2"
        echo "  sudo systemctl start byob-web"
        echo "  sudo systemctl start byob-c2"
        echo ""
        echo "To start with Docker Compose (from repo root):"
        echo "  docker-compose up -d"
        echo ""
        echo "Access the web interface at: http://command.lan"
        echo "Note: Edit /etc/nginx/sites-available/byob to add other server IPs for load balancing"
    fi
    exit
    ;;
esac
