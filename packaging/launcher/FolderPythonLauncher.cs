// dep-007 / hotspot #6: native entry contains no Python, torch or model DLLs.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

internal static class FolderPythonLauncher {
    private const string RelativeScript = "__SCRIPT_REL__";
    private static string Quote(string value) {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { result.Append('\\', slashes * 2 + 1); result.Append(c); }
            else { result.Append('\\', slashes); result.Append(c); }
            slashes = 0;
        }
        result.Append('\\', slashes * 2); result.Append('"');
        return result.ToString();
    }
    [STAThread]
    private static int Main(string[] args) {
        string root = null;
        try {
            var directory = new DirectoryInfo(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location));
            while (directory != null) {
                if (File.Exists(Path.Combine(directory.FullName, "DEPLOY.bat")) &&
                    Directory.Exists(Path.Combine(directory.FullName, "packaging"))) { root = directory.FullName; break; }
                directory = directory.Parent;
            }
            if (root == null) throw new Exception("EVS installation root was not found.");
            string python = Path.Combine(root, "runtime/python310/python.exe");
            string script = Path.Combine(root, RelativeScript);
            if (!File.Exists(python) || !File.Exists(script))
                throw new Exception("Please run DEPLOY.bat in the installation folder first.");
            var start = new ProcessStartInfo(python);
            start.Arguments = Quote(script);
            foreach (string arg in args) start.Arguments += " " + Quote(arg);
            start.WorkingDirectory = Path.GetDirectoryName(script);
            start.UseShellExecute = false; start.CreateNoWindow = true;
            start.RedirectStandardError = true; start.RedirectStandardOutput = true;
            foreach (string key in new[] { "PYTHONHOME", "PYTHONPATH", "PIP_TARGET", "PIP_PREFIX", "PIP_USER" })
                start.EnvironmentVariables.Remove(key);
            start.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
            start.EnvironmentVariables["PIP_CONFIG_FILE"] = "NUL";
            start.EnvironmentVariables["THA4_PORTABLE_ROOT"] = root;
            foreach (string key in new[] { "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "PYTHONPYCACHEPREFIX", "MPLCONFIGDIR", "TORCH_HOME", "HF_HOME" }) {
                string cache = Path.Combine(root, "workspace/cache/" + key.ToLowerInvariant());
                Directory.CreateDirectory(cache); start.EnvironmentVariables[key] = cache;
            }
            string logDirectory = Path.Combine(root, "workspace/logs");
            Directory.CreateDirectory(logDirectory);
            string log = Path.Combine(logDirectory, Path.GetFileNameWithoutExtension(Assembly.GetExecutingAssembly().Location) + "-native.log");
            object writeLock = new object();
            using (Process child = new Process()) {
                child.StartInfo = start;
                DataReceivedEventHandler write = delegate(object sender, DataReceivedEventArgs e) {
                    if (e.Data != null) lock (writeLock) File.AppendAllText(log, e.Data + Environment.NewLine, Encoding.UTF8);
                };
                child.OutputDataReceived += write; child.ErrorDataReceived += write;
                child.Start(); child.BeginOutputReadLine(); child.BeginErrorReadLine();
                child.WaitForExit(); return child.ExitCode;
            }
        } catch (Exception error) {
            if (root != null) {
                try { Directory.CreateDirectory(Path.Combine(root,"workspace/logs"));
                    File.AppendAllText(Path.Combine(root,"workspace/logs/native-launch-error.log"),error.ToString()+Environment.NewLine); } catch { }
            }
            MessageBox.Show(error.Message, "EasyVtuberStudio", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
