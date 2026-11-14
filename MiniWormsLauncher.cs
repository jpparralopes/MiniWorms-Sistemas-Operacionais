using System;
using System.IO;
using System.Diagnostics;
using System.Windows.Forms;

internal static class MiniWormsLauncher
{
    [STAThread]
    public static void Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string batch = Path.Combine(root, "INICIAR_DEMO_WINDOWS.bat");
        foreach (string required in new string[] {"cliente.py", "servidor.py", "jogo.py", "motor.py", "INICIAR_DEMO_WINDOWS.bat"})
        {
            if (!File.Exists(Path.Combine(root, required)))
            {
                MessageBox.Show("Arquivo ausente: " + required + ". Extraia o ZIP inteiro antes de iniciar.", "Mini Worms");
                return;
            }
        }
        try
        {
            Process p = Process.Start(new ProcessStartInfo {
                FileName = batch,
                WorkingDirectory = root,
                UseShellExecute = true,
                WindowStyle = ProcessWindowStyle.Normal
            });
            if (p == null)
                MessageBox.Show("Falha ao iniciar o Mini Worms.", "Mini Worms");
        }
        catch (Exception ex)
        {
            MessageBox.Show("Nao foi possivel iniciar o jogo: " + ex.Message, "Mini Worms");
        }
    }
}