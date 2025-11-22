#!/usr/bin/env python3
"""
Iran Network Health Check Tool - SOLID Version
Modern, maintainable, and extensible network diagnostics
"""

import socket
import subprocess
import platform
import argparse
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import requests

# Disable SSL warnings
try:
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
except:
    pass

# Domain Models
@dataclass(frozen=True)
class TestResult:
    success: bool
    target: str
    latency: float = 0.0
    packet_loss: float = 0.0
    response_time: float = 0.0
    status_code: int = 0
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

# Interfaces
class ConfigProvider(ABC):
    @abstractmethod
    def load_config(self) -> Dict: ...

class NetworkTest(ABC):
    @abstractmethod
    def execute(self) -> TestResult: ...

class ResultPublisher(ABC):
    @abstractmethod
    def publish(self, results: List[TestResult]) -> None: ...

# Implementations
class JSONConfigProvider(ConfigProvider):
    def __init__(self, config_path: str = "network_config_solid.json"):
        self.config_path = Path(config_path)
    
    def load_config(self) -> Dict:
        default_config = {
            "ping_targets": ["8.8.8.8", "1.1.1.1"],
            "http_targets": [
                "https://digikala.com",
                "https://academy.mci.ir", 
                "https://youtube.com",
                "https://instagram.com",
                "https://snapp.ir"
            ],
            "timeouts": {"ping": 8, "http": 12},
            "tcp_ports": [{"host": "8.8.8.8", "port": 53}]
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
                
        # Save default config
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        return default_config

class PingTest(NetworkTest):
    def __init__(self, host: str, timeout: int = 8):
        self.host = host
        self.timeout = timeout
    
    def execute(self) -> TestResult:
        if not self._validate_target():
            return TestResult(
                success=False,
                target=self.host,
                error="Invalid target"
            )
        
        try:
            param = "-n" if platform.system() == "Windows" else "-c"
            cmd = f"ping {param} 2 {self.host}"
            result = subprocess.check_output(cmd, shell=True, text=True, timeout=self.timeout)
            
            latency, packet_loss = self._parse_output(result)
            
            return TestResult(
                success=True,
                target=self.host,
                latency=latency,
                packet_loss=packet_loss
            )
            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception) as e:
            return TestResult(
                success=False,
                target=self.host,
                error=f"Ping failed: {str(e)}"
            )
    
    def _validate_target(self) -> bool:
        return bool(self.host and self.host != "Unknown")
    
    def _parse_output(self, output: str) -> Tuple[float, float]:
        try:
            if platform.system() == "Windows":
                if "Average" in output:
                    for line in output.splitlines():
                        if "Average" in line and "ms" in line:
                            latency = int(line.split("=")[1].split("ms")[0].strip())
                            return latency, 0.0
            else:
                # Linux/Mac
                if "min/avg/max" in output:
                    for line in output.splitlines():
                        if "min/avg/max" in line:
                            parts = line.split("=")[1].split("/")
                            if len(parts) >= 2:
                                latency = float(parts[1])
                                return latency, 0.0
        except:
            pass
        return 0.0, 100.0

class HTTPTest(NetworkTest):
    def __init__(self, url: str, timeout: int = 12):
        self.url = url
        self.timeout = timeout
    
    def execute(self) -> TestResult:
        try:
            start_time = time.time()
            response = requests.get(
                self.url, 
                timeout=self.timeout, 
                verify=False,
                allow_redirects=True
            )
            response_time = (time.time() - start_time) * 1000
            
            return TestResult(
                success=response.status_code < 400,
                target=self.url,
                response_time=response_time,
                status_code=response.status_code
            )
            
        except Exception as e:
            return TestResult(
                success=False,
                target=self.url,
                error=f"HTTP request failed: {str(e)}"
            )

class TCPTest(NetworkTest):
    def __init__(self, host: str, port: int, timeout: int = 6):
        self.host = host
        self.port = port
        self.timeout = timeout
    
    def execute(self) -> TestResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout):
                return TestResult(
                    success=True,
                    target=f"{self.host}:{self.port}",
                    response_time=0.0
                )
        except Exception as e:
            return TestResult(
                success=False,
                target=f"{self.host}:{self.port}",
                error=f"TCP connection failed: {str(e)}"
            )

class TestOrchestrator:
    def __init__(self, config_provider: ConfigProvider):
        self.config_provider = config_provider
        self.config = config_provider.load_config()
    
    def create_test_suite(self) -> List[NetworkTest]:
        tests = []
        
        # Add ping tests
        for target in self.config.get("ping_targets", []):
            tests.append(PingTest(target, self.config["timeouts"]["ping"]))
        
        # Add HTTP tests
        for target in self.config.get("http_targets", []):
            tests.append(HTTPTest(target, self.config["timeouts"]["http"]))
        
        # Add TCP tests
        for tcp_test in self.config.get("tcp_ports", []):
            tests.append(TCPTest(
                tcp_test["host"], 
                tcp_test["port"], 
                self.config["timeouts"].get("tcp", 6)
            ))
        
        return tests
    
    def run_tests(self) -> List[TestResult]:
        tests = self.create_test_suite()
        results = []
        
        for test in tests:
            result = test.execute()
            results.append(result)
        
        return results

class RichResultPublisher(ResultPublisher):
    def __init__(self):
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.panel import Panel
            from rich.align import Align
            self.console = Console()
            self.Panel = Panel
            self.Align = Align
            self.Table = Table
            self.has_rich = True
        except ImportError:
            self.has_rich = False
    
    def publish(self, results: List[TestResult]) -> None:
        if self.has_rich:
            self._publish_rich(results)
        else:
            self._publish_text(results)
    
    def _publish_rich(self, results: List[TestResult]):
        # Header
        self.console.print(self.Panel(
            self.Align.center("🇮🇷 Iran Network Health Check Tool - SOLID VERSION 🇮🇷"),
            style="bold cyan"
        ))
        
        # Ping Tests Table
        ping_results = [r for r in results if "ping" in r.target.lower() or ":" not in r.target and not r.target.startswith("http")]
        if ping_results:
            ping_table = self.Table(show_header=True, header_style="bold green")
            ping_table.add_column("Target", style="cyan", width=20)
            ping_table.add_column("Status", justify="center", width=10)
            ping_table.add_column("Latency", justify="right", width=12)
            ping_table.add_column("Packet Loss", justify="right", width=12)
            
            for result in ping_results:
                status = "✅" if result.success else "❌"
                latency = f"{result.latency}ms" if result.success and result.latency > 0 else "N/A"
                packet_loss = f"{result.packet_loss}%" if result.success else "100%"
                ping_table.add_row(result.target, status, latency, packet_loss)
            
            self.console.print(self.Panel(ping_table, title="🔄 Ping & TCP Tests"))
        
        # HTTP Tests Table
        http_results = [r for r in results if r.target.startswith("http")]
        if http_results:
            http_table = self.Table(show_header=True, header_style="bold yellow")
            http_table.add_column("Website", style="magenta", width=30)
            http_table.add_column("Status", justify="center", width=10)
            http_table.add_column("Response Time", justify="right", width=15)
            http_table.add_column("Status Code", justify="center", width=12)
            
            for result in http_results:
                status = "✅" if result.success else "❌"
                response_time = f"{result.response_time:.1f}ms" if result.success else "N/A"
                status_code = str(result.status_code) if result.success else "N/A"
                display_url = result.target.replace('https://', '')[:28]
                if len(display_url) > 28:
                    display_url = display_url[:25] + "..."
                http_table.add_row(display_url, status, response_time, status_code)
            
            self.console.print(self.Panel(http_table, title="🌐 HTTP Connectivity"))
        
        # Diagnosis
        self._print_diagnosis(results)
    
    def _print_diagnosis(self, results: List[TestResult]):
        mci_results = [r for r in results if "mci.ir" in r.target]
        youtube_results = [r for r in results if "youtube.com" in r.target]
        
        mci_accessible = any(r.success for r in mci_results)
        youtube_accessible = any(r.success for r in youtube_results)
        
        self.console.print("\n[bold]Diagnosis:[/]")
        if mci_accessible:
            self.console.print("[bold green]✅ MCI Academy is working normally[/]")
        elif youtube_accessible:
            self.console.print("[bold yellow]⚠️ MCI Academy blocked due to active VPN/Foreign IP[/]")
        else:
            self.console.print("[bold red]❌ MCI Academy unreachable - Network restrictions detected[/]")
        
        # Overall Status
        overall_status = "HEALTHY" if mci_accessible else "ISSUES DETECTED"
        status_color = "green" if mci_accessible else "red"
        
        self.console.print(self.Panel(
            self.Align.center(f"Overall Status: [{status_color}]{overall_status}[/] | SOLID Architecture"),
            style=f"bold {status_color}"
        ))
    
    def _publish_text(self, results: List[TestResult]):
        print("Network Test Results - SOLID Version")
        print("=" * 50)
        for result in results:
            status = "PASS" if result.success else "FAIL"
            print(f"{result.target}: {status}")

# Factory for creating different components
class NetworkFactory:
    @staticmethod
    def create_config_provider() -> ConfigProvider:
        return JSONConfigProvider()
    
    @staticmethod
    def create_publisher() -> ResultPublisher:
        return RichResultPublisher()
    
    @staticmethod
    def create_orchestrator() -> TestOrchestrator:
        return TestOrchestrator(NetworkFactory.create_config_provider())

# Main application
def main():
    parser = argparse.ArgumentParser(description="Iran Network Health Check Tool - SOLID Version")
    parser.add_argument("--watch", action="store_true", help="Monitor mode")
    parser.add_argument("--interval", type=int, default=60, help="Refresh interval in seconds")
    
    args = parser.parse_args()
    
    # Dependency Injection using Factory
    orchestrator = NetworkFactory.create_orchestrator()
    publisher = NetworkFactory.create_publisher()
    
    try:
        if args.watch:
            print("🚀 Starting SOLID Network Monitoring... (Press Ctrl+C to stop)")
            iteration = 0
            while True:
                iteration += 1
                print(f"\n--- Check #{iteration} at {datetime.now().strftime('%H:%M:%S')} ---")
                
                results = orchestrator.run_tests()
                publisher.publish(results)
                
                print(f"\nNext check in {args.interval} seconds...")
                time.sleep(args.interval)
        else:
            # Single run
            print("🔍 Running SOLID Network Analysis...")
            results = orchestrator.run_tests()
            publisher.publish(results)
                
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user. Goodbye!")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")

if __name__ == "__main__":
    main()