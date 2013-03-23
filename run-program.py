# Runs a program within the chroot
# Note: Currently only support java with runner.
import sys, json, os, subprocess, shutil

# config is a json object with the following definitions:
# - "directory": The directory that all of the data is in.
# - "lang": The language. Must be "JavaWithRunner"
# - "filename": The name of the student's submission
# - "runner_name": The name of the runner to use
#config = json.loads(sys.stdin.read())

directory = sys.stdin.read()

config = json.loads(open("root/%s/pc3-config"%directory).read())

shutil.copytree("root/%s"%directory, "run-dir/%s"%directory)
shutil.copyfile("data/runners/%s.java"%config["runner_name"], "run-dir/%s/%s.java"%(directory, config["runner_name"]))
os.chdir("run-dir/%s"%directory) # A directory we own

# Now, run stuff....
def handle_JavaWithRunner(filename, runner_name):
    runtime = 0.0
    compiler_output = ""
    output = ""
    did_run = True
    try:
        CHUSER = "sudo -u pc3-user"
        compiler_output += subprocess.check_output(["javac", "-C", "%s"%filename], stderr=subprocess.STDOUT)
        compiler_output += subprocess.check_output(["javac", "-C", "%s.java"%runner_name], stderr=subprocess.STDOUT)
        output += subprocess.check_output(["java", "%s"%runner_name], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output += e.output
        did_run = False
    return (did_run, compiler_output, output, runtime)

print json.dumps(handle_JavaWithRunner(config["filename"], config["runner_name"]))
