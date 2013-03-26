PC3
===

> "... That Lane guy still has no clue."
> The history of PC2.

Mr. Stephen's more awesomer version of PC2.

Install
=======

Alright, install is fairly simply. It's a two-step process, depending on how you count the steps:
1. Install a blank copy of Ubuntu Server 12.04 onto a computer or virtual machine. Either will work. You can make the user whatever you want, but be certain that the computer has access to the internet.
2. Download and run the postinstall.sh script as sudo by typing "wget http://pillow.rscheme.org/postinstall.sh && chmod +x postinstall.sh && sudo ./postinstall.sh" and entering your password when prompted.
3. Profit! The postinstall.sh script will print out your root username and password. Start the server by typing "sudo /etc/init.d/pc3 start" in a terminal and entering your password if prompted.
