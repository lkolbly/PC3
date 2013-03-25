mongodump -d pc3
tar c data/ run-dir/ dump/pc3 | gzip -c > pc3-export.`date +%y%m%d`.tgz
