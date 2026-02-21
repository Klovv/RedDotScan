#!/usr/bin/env python3
import sys
import subprocess
import socket
import re
import os

# Colores para la terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_banner():
    print(f"{Colors.HEADER}{Colors.BOLD}")
    print(r"""
    ____       ____        __  _____
   / __ \___  / __ \____  / /_/ ___/_________ _____
  / /_/ / _ \/ / / / __ \/ __/\__ \/ ___/ __ `/ __ \
 / _, _/  __/ /_/ / /_/ / /_ ___/ / /__/ /_/ / / / /
/_/ |_|\___/_____/\____/\__//____/\___/\__,_/_/ /_/ 
    v1.0 - Initial Recon & Roadmap Generator
    Created for Kali Linux
    """)
    print(f"{Colors.ENDC}")

def check_root():
    if os.geteuid() != 0:
        print(f"{Colors.FAIL}[!] Este script debe ejecutarse como root para que Nmap funcione correctamente (detección de OS).{Colors.ENDC}")
        print(f"{Colors.WARNING}Uso: sudo python3 {sys.argv[0]} <target>{Colors.ENDC}")
        sys.exit(1)

def check_dependency(tool_name):
    """Verifica si una herramienta está instalada en el sistema."""
    from shutil import which
    return which(tool_name) is not None

def get_target_ip(target):
    """Resuelve el dominio a IP si es necesario."""
    try:
        ip = socket.gethostbyname(target)
        return ip
    except socket.gaierror:
        print(f"{Colors.FAIL}[!] No se pudo resolver el host: {target}{Colors.ENDC}")
        sys.exit(1)

def run_command(command):
    """Ejecuta un comando de sistema y devuelve la salida."""
    try:
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
        return result.decode('utf-8')
    except subprocess.CalledProcessError as e:
        return e.output.decode('utf-8')

def analyze_host(target, ip, stealth_mode=False):
    print(f"{Colors.BLUE}[*] Iniciando escaneo {'sigiloso' if stealth_mode else 'básico'} sobre {target} ({ip})...{Colors.ENDC}")

    # Construir el comando de Nmap según el modo
    if stealth_mode:
        # Escaneo sigiloso: SYN scan (-sS), sin resolución DNS (-n), sin detección de OS (-Pn)
        nmap_cmd = f"nmap -sS -n -Pn -p- {ip}"
    else:
        # Escaneo básico: detección de versiones y OS
        nmap_cmd = f"nmap -sV -O -F --version-light {ip}"

    if not check_dependency("nmap"):
        print(f"{Colors.FAIL}[!] Nmap no está instalado. Instálalo con: sudo apt install nmap{Colors.ENDC}")
        sys.exit(1)

    print(f"{Colors.GREEN}[+] Ejecutando: {nmap_cmd}{Colors.ENDC}")
    nmap_output = run_command(nmap_cmd)
    print(nmap_output)

    return nmap_output

def generate_roadmap(nmap_output, target, ip):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== ROADMAP DE ANÁLISIS RECOMENDADO ==={Colors.ENDC}")
    
    suggestions = []
    
    # Detectar Sistema Operativo
    if "Windows" in nmap_output:
        os_type = "Windows"
        print(f"{Colors.WARNING}[+] Sistema detectado: Windows{Colors.ENDC}")
        suggestions.append({
            "type": "OS",
            "msg": "Enumeración de Windows",
            "cmds": [
                f"nmap -p 445 --script smb-vuln* {ip} # Buscar vulnerabilidades SMB",
                f"enum4linux -a {ip} # Enumeración completa de usuarios/shares (si SMB está abierto)"
            ]
        })
    elif "Linux" in nmap_output:
        os_type = "Linux"
        print(f"{Colors.WARNING}[+] Sistema detectado: Linux{Colors.ENDC}")
        suggestions.append({
            "type": "OS",
            "msg": "Enumeración de Linux",
            "cmds": [
                f"nmap -p 22 --script ssh-auth-methods {ip} # Revisar métodos de autenticación SSH"
            ]
        })
    else:
        print(f"{Colors.WARNING}[?] Sistema Operativo no identificado con certeza.{Colors.ENDC}")

    # Análisis de Puertos
    open_ports = re.findall(r"(\d+)/tcp\s+open", nmap_output)
    
    # Web (80, 443, 8080)
    if any(p in open_ports for p in ['80', '443', '8080']):
        print(f"{Colors.BLUE}[+] Servicios Web detectados.{Colors.ENDC}")
        web_cmds = [
            f"whatweb {target} # Identificar tecnologías web",
            f"nikto -h {target} # Escáner de vulnerabilidades web básico",
            f"gobuster dir -u http://{target} -w /usr/share/wordlists/dirb/common.txt # Fuzzing de directorios"
        ]
        
        # Wordpress específico
        if "WordPress" in nmap_output: # Simple check, nmap -sV might show it
             web_cmds.append(f"wpscan --url http://{target} # Escáner especializado en WordPress")
             
        suggestions.append({
            "type": "Service",
            "msg": "Análisis Web",
            "cmds": web_cmds
        })

    # SMB (445, 139)
    if any(p in open_ports for p in ['445', '139']):
        print(f"{Colors.BLUE}[+] SMB detectado.{Colors.ENDC}")
        suggestions.append({
            "type": "Service",
            "msg": "Análisis SMB",
            "cmds": [
                f"smbclient -L /////{ip} # Listar recursos compartidos",
                f"crackmapexec smb {ip} # Información del dominio y versiones"
            ]
        })

    # DNS (53)
    if '53' in open_ports:
         suggestions.append({
            "type": "Service",
            "msg": "Análisis DNS",
            "cmds": [
                f"dig axfr @{ip} {target if target != ip else 'domain.com'} # Intentar transferencia de zona",
                f"dnsrecon -d {target} # Reconocimiento DNS"
            ]
        })

    # FTP (21)
    if '21' in open_ports:
        suggestions.append({
            "type": "Service",
            "msg": "Análisis FTP",
            "cmds": [
                f"nmap --script ftp-anon {ip} -p 21 # Verificar login anónimo",
                f"hydra -L /usr/share/wordlists/metasploit/unix_users.txt -P /usr/share/wordlists/rockyou.txt ftp://{ip} # Fuerza bruta (con cuidado)"
            ]
        })

    # Base de Datos (3306 MySQL, 5432 PostgreSQL)
    if '3306' in open_ports:
         suggestions.append({
            "type": "Service",
            "msg": "Análisis MySQL",
            "cmds": [f"nmap --script mysql-info {ip} -p 3306"]
        })
    
    # Imprimir sugerencias
    if not suggestions:
        print(f"{Colors.FAIL}[!] No hay sugerencias específicas. Realiza un escaneo completo de puertos:{Colors.ENDC}")
        print(f"nmap -p- -sS -A {ip}")
    else:
        for item in suggestions:
            print(f"\n{Colors.GREEN}--- {item['msg']} ---{Colors.ENDC}")
            for cmd in item['cmds']:
                print(f"  $ {cmd}")

    print(f"\n{Colors.HEADER}=== HERRAMIENTAS ADICIONALES SUGERIDAS (GITHUB) ==={Colors.ENDC}")
    print("1. PEASS-ng (Privilege Escalation): https://github.com/carlospolop/PEASS-ng")
    print("2. SecLists (Wordlists): https://github.com/danielmiessler/SecLists")
    if "Windows" in nmap_output or any(p in open_ports for p in ['445', '139']):
         print("3. Impacket (Network Protocols): https://github.com/fortra/impacket")

def get_local_info():
    """Obtiene la IP y la dirección MAC de la máquina local."""
    try:
        # Obtener la IP local
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        # Obtener la dirección MAC
        import uuid
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8 * 6, 8)][::-1])

        print(f"{Colors.GREEN}[+] IP Local: {local_ip}{Colors.ENDC}")
        print(f"{Colors.GREEN}[+] Dirección MAC: {mac}{Colors.ENDC}")
    except Exception as e:
        print(f"{Colors.FAIL}[!] Error al obtener la información local: {e}{Colors.ENDC}")

def main():
    print_banner()

    if len(sys.argv) < 2:
        print(f"{Colors.WARNING}Uso: sudo python3 {sys.argv[0]} <ip_o_dominio> [--stealth] [--local-info]{Colors.ENDC}")
        sys.exit(1)

    if "--local-info" in sys.argv:
        get_local_info()
        sys.exit(0)

    check_root()

    target = sys.argv[1]
    stealth_mode = "--stealth" in sys.argv
    ip = get_target_ip(target)

    if check_dependency("nmap"):
        output = analyze_host(target, ip, stealth_mode)
        generate_roadmap(output, target, ip)
    else:
        print(f"{Colors.FAIL}[!] Error crítico: Nmap no encontrado.{Colors.ENDC}")

if __name__ == "__main__":
    main()
