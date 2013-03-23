# Runs a program within the chroot
# Note: Currently only support java with runner.
import sys, json, os, subprocess, shutil, time

# config is a json object with the following definitions:
# - "directory": The directory that all of the data is in.
# - "lang": The language. Must be "JavaWithRunner"
# - "filename": The name of the student's submission
# - "runner_name": The name of the runner to use
#config = json.loads(sys.stdin.read())

directory = sys.stdin.read().strip()

config = json.loads(open("root/%s/pc3-config"%directory).read())

shutil.copytree("root/%s"%directory, "run-dir/%s"%directory)
shutil.copyfile("data/runners/%s.java"%config["runner_name"], "run-dir/%s/%s.java"%(directory, config["runner_name"]))
os.chdir("run-dir/%s"%directory) # A directory we own

# Now, run stuff....
def handle_JavaWithRunner(filename, runner_name):
    MAX_TIME = 5.0
    runtime = 0.0
    compiler_output = ""
    output = ""
    did_run = True
    try:
        CHUSER = "sudo -u pc3-user"
        compiler_output += subprocess.check_output(["javac", "-C", "%s"%filename], stderr=subprocess.STDOUT)
        compiler_output += subprocess.check_output(["javac", "-C", "%s.java"%runner_name], stderr=subprocess.STDOUT)
        output += subprocess.check_output(["java", "%s"%runner_name], stderr=subprocess.STDOUT)
        p = subprocess.Popen(["java", runner_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        start_time = time.time()
        while True:
            time.sleep(0.25)
            if time.time() - start_time > MAX_TIME:
                output += p.stdout.read()
                output += "\n*** PC3 ERROR: PROCESS TIMEOUT ***\n"
                p.kill()
                break
            rval = p.poll()
            if rval:
                output += p.stdout.read()
                break
    except subprocess.CalledProcessError as e:
        output += e.output
        did_run = False
    return (did_run, compiler_output, output, runtime)

if config["lang"] == "JavaWithRunner":
    print json.dumps(handle_JavaWithRunner(config["filename"], config["runner_name"]))
else:
    print json.dumps({"error": "unknown language '%s'"%config["lang"]})
