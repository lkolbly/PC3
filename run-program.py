# Runs a program within the chroot
# Note: Currently only support java with runner.
import sys, json, os, subprocess, shutil, time, StringIO, tarfile

# config is a json object with the following definitions:
# - "directory": The directory that all of the data is in.
# - "lang": The language. Must be "JavaWithRunner"
# - "filename": The name of the student's submission
# - "runner_name": The name of the runner to use
#config = json.loads(sys.stdin.read())

directory = sys.stdin.read().strip()

config = json.loads(open("root/%s/pc3-config"%directory).read())
if "runner_name" in config:
    if ".java" not in config["runner_name"] and config["lang"] == "JavaWithRunner":
        config["runner_name"] += ".java"

shutil.copytree("root/%s"%directory, "run-dir/%s"%directory)
if "runner_name" in config:
    shutil.copyfile("data/runners/%s"%config["runner_name"], "run-dir/%s/%s"%(directory, config["runner_name"]))
if "input_files" in config:
    shutil.copyfile("data/%s/archive.tar"%config["problem_directory"], "run-dir/%s/archive.tar"%(directory))
os.chdir("run-dir/%s"%directory) # A directory we own
if "input_files" in config:
    # Extract them
    tar = tarfile.open("archive.tar")
    tar.extractall(".")
    tar.close()

COMPILERS = {"java": lambda filename: "javac -C %s"%filename}
RUNNERS = {"java": lambda classname: "java %s"%".".join(classname.split(".")[:-1]),
           "python2": lambda filename: "python2 %s"%filename}

def getLangWithRunnerCommands(language, filename, runner_name):
    # Compile...
    compile_commands = []
    if language in COMPILERS:
        compile_commands.append(COMPILERS[language](filename))
        compile_commands.append(COMPILERS[language](runner_name))
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
        run_commands.append("cat %s"%i + RUNNERS[language](filename))
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
def handle_LangWithRunner(language, filename, runner_name):
    MAX_TIME = 10.0
    runtime = 0.0
    compiler_output = ""
    output = ""
    did_run = True
    output_matches = True
    try:
        cmds = getLangWithRunnerCommands(language, filename, runner_name)
        for cmd in cmds["compile"]:
            if len(cmd) > 0:
                compiler_output += "# %s\n"%str(cmd.split(" "))
                compiler_output += subprocess.check_output(cmd.split(" "), stderr=subprocess.STDOUT)
        output, runtime, status = runProgram(cmds["run"][0])
    except subprocess.CalledProcessError as e:
        output += e.output
        did_run = False
    return (did_run, compiler_output, output, runtime, output_matches)

def handle_LangWithInput(language, filename, input_files, redacted=True):
    runtime = 0.0
    compiler_output = ""
    output = ""
    did_run = True
    output_matches = True
    try:
        cmds = getLangWithInputCommands(language, filename, input_files)
        for cmd in cmds["compile"]:
            if len(cmd) > 0:
                compiler_output += "# %s\n"%str(cmd.split(" "))
                compiler_output += subprocess.check_output(cmd.split(" "), stderr=subprocess.STDOUT)
        cnt = 0
        for cmd in cmds["run"]:
            prog_output, prog_runtime, status = runProgram(cmds["run"][0])
            runtime += prog_runtime
            if not redacted:
                output += prog_output
            expected_out = open("%s.out"%input_files[cnt]).read()
            if prog_output != expected_out:
                output_matches = False
        if redacted:
            output += "*** OUTPUT IS REDACTED ***\n"
        if not output_matches:
            output += "*** ONE OR MORE TEST CASE(S) WERE INCORRECT ***\n"
    except subprocess.CalledProcessError as e:
        output += e.output
        did_run = False
    return (did_run, compiler_output, output, runtime, output_matches)

if isinstance(config["lang"], basestring):
    if config["lang"] == "JavaWithRunner":
        print json.dumps(handle_LangWithRunner("java", config["filename"], config["runner_name"]))
    elif config["lang"] == "Python2WithInput":
        print json.dumps(handle_LangWithInput("python2", config["filename"], config["input_files"]))
    else:
        print json.dumps({"error": "unknown language '%s'"%config["lang"]})
else:
    if config["lang"]["type"] == "runner":
        retval = handle_LangWithRunner(config["lang"]["lang"], config["filename"], config["runner_name"])
    elif config["lang"]["type"] == "inputfiles":
        retval = handle_LangWithInput(config["lang"]["lang"], config["filename"], config["input_files"])
    else:
        retval = {"error": "unknown language '%s'"%config["lang"]}
    print json.dumps(retval)
