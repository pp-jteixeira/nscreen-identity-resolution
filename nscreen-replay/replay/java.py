"""Build and invoke original Java code without Spark or Hive runtimes."""

import hashlib
import os
import re
import subprocess
import urllib.request
from pathlib import Path

FASTUTIL_VERSION = "8.1.1"
ROOT = Path(__file__).resolve().parents[1]


def java_home():
    candidates = [
        os.environ.get("JAVA_HOME", ""),
        "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home",
        "/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home",
    ]
    for candidate in candidates:
        if candidate and (Path(candidate) / "bin/javac").is_file():
            return Path(candidate)
    raise RuntimeError("Set JAVA_HOME to a JDK 17 or newer")


def sources(forge):
    base = forge / "src/jvm/com/pulsepoint"
    udf = base / "hive/udf"
    return [
        ROOT / "java/ReplayBridge.java",
        udf / "calcscreen7ids/ResultEntry.java",
        udf / "calcscreen7ids/calc/Screen7IdCalculator.java",
        udf / "calcscreen7ids/calc/Screen7IdCalculatorDHMH.java",
        udf / "calcscreen7ids/calc/Pair.java",
        base / "udf/ssus/udf/MurmurHash.java",
        *sorted((udf / "louvain").glob("*.java")),
    ]


def fingerprint(forge):
    evaluator = (
        forge
        / "src/jvm/com/pulsepoint/hive/udf/calcscreen7ids/UDAFCalcScreen7IdsEvaluator.java"
    )
    if not re.search(r"new\s+Screen7IdCalculatorDHMH\s*\(\s*\)", evaluator.read_text()):
        raise RuntimeError(
            "Production calculator selection changed; update the Java bridge explicitly"
        )
    return hashlib.sha256(b"".join(p.read_bytes() for p in sources(forge))).hexdigest()


def build(forge):
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    jar = cache / f"fastutil-{FASTUTIL_VERSION}.jar"
    url = f"https://repo.maven.apache.org/maven2/it/unimi/dsi/fastutil/{FASTUTIL_VERSION}/{jar.name}"
    checksum = cache / (jar.name + ".sha1")
    if not checksum.exists():
        with urllib.request.urlopen(url + ".sha1", timeout=60) as response:
            checksum.write_bytes(response.read())
    if not jar.exists():
        part = jar.with_suffix(".part")
        with (
            urllib.request.urlopen(url, timeout=60) as response,
            part.open("wb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        part.replace(jar)
    if (
        hashlib.sha1(jar.read_bytes()).hexdigest()
        != checksum.read_text().strip().split()[0]
    ):
        raise RuntimeError("fastutil integrity check failed")
    classes = cache / fingerprint(forge)
    if not (classes / "ReplayBridge.class").exists():
        classes.mkdir(exist_ok=True)
        subprocess.run(
            [
                str(java_home() / "bin/javac"),
                "--release",
                "17",
                "-cp",
                str(jar),
                "-d",
                str(classes),
                *map(str, sources(forge)),
            ],
            check=True,
        )
    return classes, jar


def command(forge, heap="6g"):
    classes, jar = build(forge)
    return [
        str(java_home() / "bin/java"),
        f"-Xmx{heap}",
        "-cp",
        f"{classes}{os.pathsep}{jar}",
        "ReplayBridge",
    ]
