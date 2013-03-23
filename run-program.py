# Runs a program within the chroot
# Note: Currently only support java with runner.
import sys, json, os, subprocess, shutil, time, StringIO

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

COMPILERS = {"java": lambda filename: "javac -C %s"%filename}
RUNNERS = {"java": lambda classname: "java %s"%classname,
           "python2": lambda filename: "python2 %s"%filename}

def getLangWithRunnerCommands(language, filename, runner_name):
    # Compile...
    compile_commands = []
    if language in COMPILERS:
        compile_commands.append(COMPILERS[language](filename))
        compile_commands.append(COMPILERS[language](runner_name+".java"))
        pass

    # Run...
    run_command = []
    if language not in RUNNERS:
        # Error!
        pass
    run_command = RUNNERS[language](runner_name)
    return {"compile": compile_commands, "run": [run_command]}

def getLangWithInputCommands(language, filename, input_files=[]):
    # Compile...
    compile_commands = []
    if language in COMPILERS:
        compile_commands.append(COMPILERS[language](filename))
    
    run_commands = []
    if language not in RUNNERS:
        # Error!
        pass
    for i in input_files:
        run_commands.append(RUNNERS[language](filename)+" %s"%i)
    return {"compile": compile_commands, "run": run_commands}

def runProgram(cmd, MAX_TIME=10.0):
    f = open("pc3-output", "w")
    p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, shell=True, close_fds=True)
    output = ""
    status = ""
    start_time = time.time()
    while True:
        time.sleep(0.1)
        if time.time() - start_time > MAX_TIME:
            output += "*** PROCESS TIMEOUT ***\n"
            status = "Timeout"
            try:
                p.terminate()
            except OSError:
                output += "*** PC3 INTERNAL ERROR: OSError on terminate ***\n"
                status = "Internal Error"
                pass
            break
        rval = p.poll()
        if rval is not None:
            break
    runtime = time.time() - start_time
    output += open("pc3-output").read()
    return (output, runtime, status)

# Now, run stuff....
def handle_JavaWithRunner(filename, runner_name):
    MAX_TIME = 10.0
    runtime = 0.0
    compiler_output = ""
    output = ""
    did_run = True
    try:
        cmds = getLangWithRunnerCommands("java", filename, runner_name)
        #CHUSER = "sudo -u pc3-user"
        #compiler_output += subprocess.check_output(["javac", "-C", "%s"%filename], stderr=subprocess.STDOUT)
        #compiler_output += subprocess.check_output(["javac", "-C", "%s.java"%runner_name], stderr=subprocess.STDOUT)
        for cmd in cmds["compile"]:
            if len(cmd) > 0:
                compiler_output += "# %s\n"%str(cmd.split(" "))
                compiler_output += subprocess.check_output(cmd.split(" "), stderr=subprocess.STDOUT)
        #output += subprocess.check_output(["java", "%s"%runner_name], stderr=subprocess.STDOUT)
        #for cmd in cmds["run"]:
        #    output += subprocess.check_output(cmd.split(" "), stderr=subprocess.STDOUT)
        #stdout = StringIO.StringIO()
        #output += "%s\n"%cmds["run"].split(" ")
        output, runtime, status = runProgram(cmds["run"][0])
        """
        f = open("pc3-output", "w")
        p = subprocess.Popen(cmds["run"][0], stdout=f, stderr=subprocess.STDOUT, shell=True, close_fds=True)
        start_time = time.time()
        while True:
            time.sleep(0.1)
            if time.time() - start_time > MAX_TIME:
                #output += p.stdout.read()
                output += "*** PROCESS TIMEOUT ***\n"
                try:
                    p.terminate()
                except OSError:
                    output += "*** PC3 INTERNAL ERROR: OSError on terminate ***\n"
                    pass
                break
            rval = p.poll()
            #output += "%s"%rval+"\n"
            if rval is not None:
                #output += "Broken by %s\n"%rval
                #output += p.stdout.read()
                break
        runtime = time.time() - start_time
        output += open("pc3-output").read()#stdout.getvalue()
        """
    except subprocess.CalledProcessError as e:
        output += e.output
        did_run = False
    return (did_run, compiler_output, output, runtime)

if config["lang"] == "JavaWithRunner":
    print json.dumps(handle_JavaWithRunner(config["filename"], config["runner_name"]))
else:
    print json.dumps({"error": "unknown language '%s'"%config["lang"]})
