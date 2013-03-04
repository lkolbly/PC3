import subprocess, tempfile, os, shutil, re

# A wrapper around the perl script
# For now, works only with single-file programs.
class Moss:
    def __init__(self, userid, language="java"):
        self.uid = userid
        self.files = []
        self.language = language

    def addFile(self, filename, project_name=None, user_name=None):
        self.files.append((filename, project_name, user_name))

    def upload(self):
        # Go generate a directory structure so that moss will output
        # a happy (i.e. well-labeled) report.
        d = tempfile.mkdtemp(suffix="pc3_moss")

        for f in self.files:
            try:
                os.mkdir("%s/%s"%(d,f[1]))
            except OSError:
                pass
            shutil.copy(f[0], "%s/%s/%s"%(d,f[1],f[2]))

        # Generate the command
        shutil.copy("moss.pl", "%s"%d)
        cmd = "cd %s && perl ./moss.pl -l %s "%(d,self.language)
        for f in self.files:
            cmd += "%s/%s "%(f[1],f[2])

        # Finally, call moss.
        #print cmd
        output = subprocess.check_output(cmd, shell=True)
        url = re.search(r"(http://[^!]+\d+)", output).groups()[0]
        #print url
        return url

#m = Moss(353538543, "python")
#m.addFile("test/a.py", "project1", "lkolbly")
#m.addFile("test/b.py", "project1", "jstephens")
