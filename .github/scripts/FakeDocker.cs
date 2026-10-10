// Stands in for docker.exe, so start-windows.bat can be tested on Windows without Docker. (A .cmd
// stand-in would not do: a batch file that runs another batch file without "call" never returns.)
// Every call is appended to %FAKE_DOCKER_LOG%; FAKE_COMPOSE_VERSION and FAKE_UP_EXIT change the answers.
using System;
using System.IO;

public static class FakeDocker
{
    public static int Main(string[] args)
    {
        string call = string.Join(" ", args);
        string log = Environment.GetEnvironmentVariable("FAKE_DOCKER_LOG");
        if (!string.IsNullOrEmpty(log)) File.AppendAllText(log, call + Environment.NewLine);
        string version = Environment.GetEnvironmentVariable("FAKE_COMPOSE_VERSION") ?? "2.29.1";
        if (call == "compose version --short") { Console.WriteLine(version); return 0; }
        if (call == "compose version") { Console.WriteLine("Docker Compose version v" + version); return 0; }
        if (call.StartsWith("compose up")) return Environment.GetEnvironmentVariable("FAKE_UP_EXIT") == "1" ? 1 : 0;
        if (call.StartsWith("compose exec")) { Console.WriteLine("Demo learner ready"); return 0; }
        return 0;
    }
}
