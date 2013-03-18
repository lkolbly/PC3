debootstrap --arch=amd64 --include=openjdk-6-jre,openjdk-6-jdk squeeze ./chroot http://ftp.us.debian.org/debian
chown pc3-user:users chroot
