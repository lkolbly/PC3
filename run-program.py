# Runs a program within the chroot
# Note: Currently only support java with runner.
import sys, json, os

# config is a json object with the following definitions:
# - "directory": The directory that all of the data is in.
# - "lang": The language. Must be "JavaWithRunner"
# - "filename": The name of the student's submission
# - "runner_name": The name of the runner to use
config = json.loads(sys.stdin.read())

os.chroot("chroot/")

# Now, run stuff....
def handle_JavaWithRunner(filename, runner_name):
    output = ""
    did_run = True
    try:
        output += subprocess.check_output(["javac", "-C", "%s.java"%filename], stderr=subprocess.STDOUT)
        output += subprocess.check_output(["javac", "-C", "%s.java"%runner_name], stderr=subprocess.STDOUT)
        output += "FINISHED COMPILING...\n"
        output += subprocess.check_output(["java", "%s"%runner_name], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        output += e.output
        did_run = False
    return (did_run, output)

print json.dumps(handle_JavaWithRunner(config["filename"], config["runner_name"]))
