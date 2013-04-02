#!/bin/sh

apt-get install unzip

# Parse command line arguments
latestbuild=0
while [ $# -gt 0 ]
do
	case "$1" in
		--latest) latestbuild=1;;
		-*)       echo >&2 "usage: $0 [--latest]"
		          exit 1;;
		*) break;;
	esac
	shift
done

# This script is to be run as sudo as a post install script on Ubuntu server systems to bootstrap them for PC3.
# Create pc3-user
adduser --disabled-password --gecos pc3 pc3 --home /home/pc3
adduser --disabled-password --gecos pc3-user pc3-user --no-create-home
echo "pc3 ALL=(pc3-user) NOPASSWD: ALL" >> /etc/sudoers
cd /home/pc3

# Fetch the tarball.
if [ $latestbuild -eq 1 ]
then
	wget -O "archive.zip" https://github.com/lkolbly/PC3/archive/master.zip
	unzip archive.zip
	mv PC3-master PC3
else
	wget http://pillow.rscheme.org/PC3-latest.tar
	tar xf PC3-latest.tar
fi

# Create the required directories
mkdir PC3/data
mkdir PC3/run-dir
chown -R pc3:pc3 PC3
chown pc3-user:pc3-user PC3/run-dir

# Install the required packages.
apt-get install -y build-essential python-twisted python-pip mongodb
pip install pymongo
pip install jinja

# Seed the database
cd /home/pc3/PC3
python main.py --reset-db

# Copy the init.d script
cp pc3.initd /etc/init.d/pc3
