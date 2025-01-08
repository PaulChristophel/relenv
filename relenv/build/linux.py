# Copyright 2022-2024 VMware, Inc.
# SPDX-License-Identifier: Apache-2
"""
The linux build process.
"""
import pathlib
import tempfile
from .common import *
from ..common import arches, LINUX


ARCHES = arches[LINUX]

# Patch for Python's setup.py
PATCH = """--- ./setup.py
+++ ./setup.py
@@ -664,6 +664,7 @@
             self.failed.append(ext.name)

     def add_multiarch_paths(self):
+        return
         # Debian/Ubuntu multiarch support.
         # https://wiki.ubuntu.com/MultiarchSpec
         tmpfile = os.path.join(self.build_temp, 'multiarch')
"""


def populate_env(env, dirs):
    """
    Make sure we have the correct environment variables set.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    """
    # CC and CXX need to be to have the full path to the executable
    env["CC"] = "{}/bin/{}-gcc -no-pie".format(dirs.toolchain, env["RELENV_HOST"])
    env["CXX"] = "{}/bin/{}-g++ -no-pie".format(dirs.toolchain, env["RELENV_HOST"])
    # Add our toolchain binaries to the path. We also add the bin directory of
    # our prefix so that libtirpc can find krb5-config
    env["PATH"] = "{}/bin/:{}/bin/:{PATH}".format(dirs.toolchain, dirs.prefix, **env)
    ldflags = [
        "-Wl,--build-id=sha1",
        "-Wl,--rpath={prefix}/lib",
        "-L{prefix}/lib",
        "-L{}/{RELENV_HOST}/sysroot/lib".format(dirs.toolchain, **env),
        "-static-libstdc++",
    ]
    env["LDFLAGS"] = " ".join(ldflags).format(prefix=dirs.prefix)
    cflags = [
        "-g",
        "-I{prefix}/include",
        "-I{prefix}/include/readline",
        "-I{prefix}/include/ncursesw",
        "-I{}/{RELENV_HOST}/sysroot/usr/include".format(dirs.toolchain, **env),
    ]
    env["CFLAGS"] = " ".join(cflags).format(prefix=dirs.prefix)
    # CPPFLAGS are needed for Python's setup.py to find the 'nessicery bits'
    # for things like zlib and sqlite.
    cpplags = [
        "-I{prefix}/include",
        "-I{prefix}/include/readline",
        "-I{prefix}/include/ncursesw",
        "-I{}/{RELENV_HOST}/sysroot/usr/include".format(dirs.toolchain, **env),
    ]
    env["CPPFLAGS"] = " ".join(cpplags).format(prefix=dirs.prefix)
    env["CXXFLAGS"] = " ".join(cpplags).format(prefix=dirs.prefix)
    env["LD_LIBRARY_PATH"] = "{prefix}/lib"
    env["PKG_CONFIG_PATH"] = f"{dirs.prefix}/lib/pkgconfig"


def build_bzip2(env, dirs, logfp):
    """
    Build bzip2.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    runcmd(
        [
            "make",
            "-j8",
            "PREFIX={}".format(dirs.prefix),
            "LDFLAGS={}".format(env["LDFLAGS"]),
            "CFLAGS=-fPIC",
            "CC={}".format(env["CC"]),
            "BUILD={}".format("x86_64-linux-gnu"),
            "HOST={}".format(env["RELENV_HOST"]),
            "install",
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(
        [
            "make",
            "-f",
            "Makefile-libbz2_so",
            "CC={}".format(env["CC"]),
            "LDFLAGS={}".format(env["LDFLAGS"]),
            "BUILD={}".format("x86_64-linux-gnu"),
            "HOST={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    shutil.copy2("libbz2.so.1.0.8", os.path.join(dirs.prefix, "lib"))


def build_libxcrypt(env, dirs, logfp):
    """
    Build libxcrypt.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            # "--enable-libgdbm-compat",
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_gdbm(env, dirs, logfp):
    """
    Build gdbm.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--enable-libgdbm-compat",
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_ncurses(env, dirs, logfp):
    """
    Build ncurses.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    configure = pathlib.Path(dirs.source) / "configure"
    if env["RELENV_BUILD_ARCH"] == "aarch64" or env["RELENV_HOST_ARCH"] == "aarch64":
        os.chdir(dirs.tmpbuild)
        runcmd([str(configure)], stderr=logfp, stdout=logfp)
        runcmd(["make", "-C", "include"], stderr=logfp, stdout=logfp)
        runcmd(["make", "-C", "progs", "tic"], stderr=logfp, stdout=logfp)
    os.chdir(dirs.source)

    # Configure with a prefix of '/' so things will be installed to '/lib'
    # instead of '/usr/local/lib'. The root of the install will be specified
    # via the DESTDIR make argument.
    runcmd(
        [
            str(configure),
            "--prefix=/",
            "--with-shared",
            "--enable-termcap",
            "--with-termlib",
            "--without-cxx-shared",
            "--without-static",
            "--without-cxx",
            "--enable-widec",
            "--without-normal",
            "--disable-stripping",
            f"--with-pkg-config={dirs.prefix}/lib/pkgconfig",
            "--enable-pc-files",
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(
        [
            "make",
            "DESTDIR={}".format(dirs.prefix),
            "TIC_PATH={}".format(str(pathlib.Path(dirs.tmpbuild) / "progs" / "tic")),
            "install",
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )


def build_readline(env, dirs, logfp):
    """
    Build readline library.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    env["LDFLAGS"] = f"{env['LDFLAGS']} -ltinfow"
    cmd = [
        "./configure",
        "--prefix={}".format(dirs.prefix),
    ]
    if env["RELENV_HOST"].find("linux") > -1:
        cmd += [
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ]
    runcmd(cmd, env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_libffi(env, dirs, logfp):
    """
    Build libffi.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--disable-multi-os-directory",
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    # libffi doens't want to honor libdir, force install to lib instead of lib64
    runcmd(
        ["sed", "-i", "s/lib64/lib/g", "Makefile"], env=env, stderr=logfp, stdout=logfp
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_zlib(env, dirs, logfp):
    """
    Build zlib.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    env["CFLAGS"] = "-fPIC {}".format(env["CFLAGS"])
    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--libdir={}/lib".format(dirs.prefix),
            "--shared",
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-no-pie", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_sasl(env, dirs, logfp):
    """
    Build cyrus-sasl.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    # Ensure position-independent code for shared libraries
    env["CFLAGS"] = "-fPIC {}".format(env.get("CFLAGS", ""))

    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--libdir={}/lib".format(dirs.prefix),  # Specify library directory
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_libyaml(env, dirs, logfp):
    """
    Build libyaml.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    # Ensure position-independent code for shared libraries
    env["CFLAGS"] = "-fPIC {}".format(env.get("CFLAGS", ""))

    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--libdir={}/lib".format(dirs.prefix),  # Specify library directory
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_libsodium(env, dirs, logfp):
    """
    Build libsodium.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    # Ensure position-independent code for shared libraries
    env["CFLAGS"] = "-fPIC {}".format(env.get("CFLAGS", ""))

    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--libdir={}/lib".format(dirs.prefix),  # Specify library directory
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_libmd(env, dirs, logfp):
    """
    Build libmd.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    # Ensure position-independent code for shared libraries
    env["CFLAGS"] = "-fPIC {}".format(env.get("CFLAGS", ""))

    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--libdir={}/lib".format(dirs.prefix),  # Specify library directory
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_libbsd(env, dirs, logfp):
    """
    Build libbsd.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    # Ensure position-independent code for shared libraries
    env["CFLAGS"] = "-fPIC {}".format(env.get("CFLAGS", ""))

    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--libdir={}/lib".format(dirs.prefix),  # Specify library directory
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
            "--enable-year2038",
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_zeromq(env, dirs, logfp):
    """
    Build zeromq.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    # Ensure position-independent code for shared libraries
    env["CFLAGS"] = f"-fPIC {env.get('CFLAGS', '')}"
    env["LDFLAGS"] = f"{env['LDFLAGS']} -lbsd -lsodium"
    env["CPPFLAGS"] += f" -I{dirs.prefix}/include"
    env["PKG_CONFIG_PATH"] = f"{dirs.prefix}/lib/pkgconfig"
    env["LD_LIBRARY_PATH"] = f"{dirs.prefix}/lib:{env.get('LD_LIBRARY_PATH', '')}"
    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--libdir={}/lib".format(dirs.prefix),  # Specify library directory
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
            "--with-libsodium",

        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_openldap(env, dirs, logfp):
    """
    Build openldap.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    # Ensure position-independent code for shared libraries
    env["CFLAGS"] = "-fPIC {}".format(env.get("CFLAGS", ""))

    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--libdir={}/lib".format(dirs.prefix),  # Specify library directory
            "--enable-shared",  # Build shared libraries
            "--disable-static",  # Optional: Disable static library building
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "depend"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_krb(env, dirs, logfp):
    """
    Build kerberos.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    if env["RELENV_BUILD_ARCH"] != env["RELENV_HOST_ARCH"]:
        env["krb5_cv_attr_constructor_destructor"] = "yes,yes"
        env["ac_cv_func_regcomp"] = "yes"
        env["ac_cv_printf_positional"] = "yes"
    os.chdir(dirs.source / "src")
    runcmd(
        [
            "./configure",
            "--prefix={}".format(dirs.prefix),
            "--without-system-verto",
            "--without-libedit",
            "--build={}".format(env["RELENV_BUILD"]),
            "--host={}".format(env["RELENV_HOST"]),
        ],
        env=env,
        stderr=logfp,
        stdout=logfp,
    )
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)


def build_python(env, dirs, logfp):
    """
    Run the commands to build Python.

    :param env: The environment dictionary
    :type env: dict
    :param dirs: The working directories
    :type dirs: ``relenv.build.common.Dirs``
    :param logfp: A handle for the log file
    :type logfp: file
    """
    env["LDFLAGS"] = "-Wl,--rpath={prefix}/lib {ldflags}".format(
        prefix=dirs.prefix, ldflags=env["LDFLAGS"]
    )

    # Needed when using a toolchain even if build and host match.
    runcmd(
        [
            "sed",
            "-i",
            "s/ac_cv_buggy_getaddrinfo=yes/ac_cv_buggy_getaddrinfo=no/g",
            "configure",
        ]
    )
    runcmd(
        [
            "sed",
            "-i",
            (
                "s/ac_cv_enable_implicit_function_declaration_error=yes/"
                "ac_cv_enable_implicit_function_declaration_error=no/g"
            ),
            "configure",
        ]
    )

    if pathlib.Path("setup.py").exists():
        with tempfile.NamedTemporaryFile(mode="w", suffix="_patch") as patch_file:
            patch_file.write(PATCH)
            patch_file.flush()
            runcmd(
                ["patch", "-p0", "-i", patch_file.name],
                env=env,
                stderr=logfp,
                stdout=logfp,
            )

    env["OPENSSL_CFLAGS"] = f"-I{dirs.prefix}/include  -Wno-coverage-mismatch"
    env["OPENSSL_LDFLAGS"] = f"-L{dirs.prefix}/lib"
    env["CFLAGS"] = f"-Wno-coverage-mismatch {env['CFLAGS']}"

    cmd = [
        "./configure",
        "-v",
        f"--prefix={dirs.prefix}",
        f"--with-openssl={dirs.prefix}",
        "--enable-optimizations",
        "--with-ensurepip=no",
        f"--build={env['RELENV_BUILD']}",
        f"--host={env['RELENV_HOST']}",
        "--disable-test-modules",
        "--with-ssl-default-suites=openssl",
        "--with-builtin-hashlib-hashes=blake2,md5,sha1,sha2,sha3",
        "--with-readline=readline",
        "--with-pkg-config=yes",
    ]

    if env["RELENV_HOST_ARCH"] != env["RELENV_BUILD_ARCH"]:
        # env["RELENV_CROSS"] = dirs.prefix
        cmd += [
            f"--with-build-python={env['RELENV_NATIVE_PY']}",
        ]
    # Needed when using a toolchain even if build and host match.
    cmd += [
        "ac_cv_file__dev_ptmx=yes",
        "ac_cv_file__dev_ptc=no",
    ]

    runcmd(cmd, env=env, stderr=logfp, stdout=logfp)
    runcmd(
        [
            "sed",
            "-i",
            "s/#readline readline.c -lreadline -ltermcap/readline readline.c -lreadline -ltinfow/g",
            "Modules/Setup",
        ]
    )
    with io.open("Modules/Setup", "a+") as fp:
        fp.seek(0, io.SEEK_END)
        fp.write("*disabled*\n" "_tkinter\n" "nsl\n" "nis\n")
    runcmd(["make", "-j8"], env=env, stderr=logfp, stdout=logfp)
    runcmd(["make", "install"], env=env, stderr=logfp, stdout=logfp)

    # RELENVCROSS=relenv/_build/aarch64-linux-gnu  relenv/_build/x86_64-linux-gnu/bin/python3 -m ensurepip
    # python = dirs.prefix / "bin" / "python3"
    # if env["RELENV_BUILD_ARCH"] == "aarch64":
    #    python = env["RELENV_NATIVE_PY"]
    # env["PYTHONUSERBASE"] = dirs.prefix
    # runcmd([str(python), "-m", "ensurepip", "-U"], env=env, stderr=logfp, stdout=logfp)


build = builds.add("linux", populate_env=populate_env, version="3.10.16")

build.add(
    "openssl",
    build_func=build_openssl,
    download={
        "url": "https://github.com/openssl/openssl/releases/download/openssl-{version}/openssl-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/openssl-{version}.tar.gz",
        "version": "3.4.0",
        "checksum": "5c2f33c3f3601676f225109231142cdc30d44127",
        "checkfunc": tarball_version,
        "checkurl": "https://www.openssl.org/source/",
    },
)


build.add(
    "openssl-fips-module",
    build_func=build_openssl_fips,
    wait_on=["openssl"],
    download={
        "url": "https://www.openssl.org/source/openssl-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/openssl-{version}.tar.gz",
        "version": "3.0.9",
        "checksum": "b569725118c0603537c9a19449046b41b39627c8",
        "checkfunc": tarball_version,
        "checkurl": "https://www.openssl.org/source/",
    },
)


build.add(
    "libxcrypt",
    download={
        "url": "https://github.com/besser82/libxcrypt/releases/download/v{version}/libxcrypt-{version}.tar.xz",
        "version": "4.4.36",
        "checksum": "c040de2fd534f84082c9c42114ba11b4e1a67635",
        "checkfunc": github_version,
        "checkurl": "https://github.com/besser82/libxcrypt/releases/",
    },
)

build.add(
    "XZ",
    download={
        "url": "http://tukaani.org/xz/xz-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/xz-{version}.tar.gz",
        "version": "5.6.2",
        "checksum": "0d6b10e4628fe08e19293c65e8dbcaade084a083",
        "checkfunc": tarball_version,
    },
)

build.add(
    name="SQLite",
    build_func=build_sqlite,
    download={
        "url": "https://sqlite.org/2024/sqlite-autoconf-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/sqlite-autoconf-{version}.tar.gz",
        "version": "3470200",
        "checksum": "40f0296080bb63f0321a5652477a6ab87c757aa2",
        "checkfunc": sqlite_version,
        "checkurl": "https://sqlite.org/",
    },
)

build.add(
    name="bzip2",
    build_func=build_bzip2,
    download={
        "url": "https://sourceware.org/pub/bzip2/bzip2-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/bzip2-{version}.tar.gz",
        "version": "1.0.8",
        "checksum": "bf7badf7e248e0ecf465d33c2f5aeec774209227",
        "checkfunc": tarball_version,
    },
)

build.add(
    name="gdbm",
    build_func=build_gdbm,
    download={
        "url": "https://ftp.gnu.org/gnu/gdbm/gdbm-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/gdbm-{version}.tar.gz",
        "version": "1.24",
        "checksum": "7bd455f28c9e4afacc042e0c712aac1b2391fef2",
        "checkfunc": tarball_version,
    },
)

build.add(
    name="ncurses",
    build_func=build_ncurses,
    download={
        "url": "https://ftp.gnu.org/pub/gnu/ncurses/ncurses-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/ncurses-{version}.tar.gz",
        # XXX: Need to work out tinfo linkage
        # "version": "6.5",
        # "checksum": "cde3024ac3f9ef21eaed6f001476ea8fffcaa381",
        "version": "6.4",
        "checksum": "bb5eb3f34b3ecd5bac8d0b58164b847f135b3d62",
        "checkfunc": tarball_version,
    },
)

build.add(
    "libffi",
    build_libffi,
    download={
        "url": "https://github.com/libffi/libffi/releases/download/v{version}/libffi-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/libffi-{version}.tar.gz",
        "version": "3.4.6",
        "checksum": "19251dfee520dff42acefe36bfe76d7168071e01",
        "checkfunc": github_version,
        "checkurl": "https://github.com/libffi/libffi/releases/",
    },
)

build.add(
    "zlib",
    build_zlib,
    download={
        "url": "https://zlib.net/fossils/zlib-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/zlib-{version}.tar.gz",
        "version": "1.3.1",
        "checksum": "f535367b1a11e2f9ac3bec723fb007fbc0d189e5",
        "checkfunc": tarball_version,
    },
)

build.add(
    "uuid",
    download={
        "url": "https://sourceforge.net/projects/libuuid/files/libuuid-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/libuuid-{version}.tar.gz",
        "version": "1.0.3",
        "checksum": "46eaedb875ae6e63677b51ec583656199241d597",
        "checkfunc": uuid_version,
    },
)

build.add(
    "krb5",
    build_func=build_krb,
    wait_on=["openssl"],
    download={
        "url": "https://kerberos.org/dist/krb5/{version}/krb5-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/krb5-{version}.tar.gz",
        "version": "1.21",
        "checksum": "e2ee531443122376ac8b62b3848d94376f646089",
        "checkfunc": krb_version,
        "checkurl": "https://kerberos.org/dist/krb5/",
    },
)

build.add(
    "readline",
    build_func=build_readline,
    wait_on=["ncurses"],
    download={
        "url": "https://ftp.gnu.org/gnu/readline/readline-{version}.tar.gz",
        "fallback_url": "https://woz.io/relenv/dependencies/readline-{version}.tar.gz",
        "version": "8.2.13",
        "checksum": "5ffb6a334c2422acbe8f4d2cb11e345265c8d930",
        "checkfunc": tarball_version,
    },
)

build.add(
    "tirpc",
    wait_on=[
        "krb5",
    ],
    download={
        "url": "https://sourceforge.net/projects/libtirpc/files/libtirpc-{version}.tar.bz2",
        # "url": "https://downloads.sourceforge.net/projects/libtirpc/files/libtirpc-{version}.tar.bz2",
        "fallback_url": "https://woz.io/relenv/dependencies/libtirpc-{version}.tar.bz2",
        "version": "1.3.6",
        "checksum": "03352908461ad2122e5be4a678893aaa2ad2ac45",
        "checkfunc": tarball_version,
    },
)

build.add(
    "openldap",
    build_func=build_openldap,
    wait_on=[
        "krb5",
    ],
    download={
        "url": "https://www.openldap.org/software/download/OpenLDAP/openldap-release/openldap-{version}.tgz",
        "fallback_url": "https://mirrors.jevincanders.net/openldap/openldap-release/openldap-{version}.tgz",
        "version": "2.5.19",
        "checksum": "efd9caaa1d36b2b940eb79f30e264b527a80e3c1",
        "checkfunc": tarball_version,
    },
)

build.add(
    "cyrus-sasl",
    build_func=build_sasl,
    wait_on=[
        "openldap",
    ],
    download={
        "url": "https://github.com/cyrusimap/cyrus-sasl/releases/download/cyrus-sasl-{version}/cyrus-sasl-{version}.tar.gz",
        "fallback_url": "https://nexus.oit.gatech.edu/relenv/dependencies/cyrus-sasl-{version}.tar.gz",
        "version": "2.1.28",
        "checksum": "c96d2ccd891904ce0118fdfcdfbd47e37a1e7543",
        "checkfunc": tarball_version,
    },
)

build.add(
    "libyaml",
    build_func=build_libyaml,
    download={
        "url": "https://github.com/yaml/libyaml/releases/download/{version}/yaml-{version}.tar.gz",
        "fallback_url": "https://nexus.oit.gatech.edu/relenv/dependencies/yaml-{version}.tar.gz",
        "version": "0.2.5",
        "checksum": "f49b39644caccabef049e3ec8859e8fdf94b686e",
        "checkfunc": tarball_version,
    },
)

build.add(
    "libsodium",
    build_func=build_libsodium,
    download={
        "url": "https://github.com/jedisct1/libsodium/releases/download/{version}-RELEASE/libsodium-{version}.tar.gz",
        "fallback_url": "https://nexus.oit.gatech.edu/relenv/dependencies/libsodium-{version}.tar.gz",
        "version": "1.0.20",
        "checksum": "e37f50e66b4b90957cfef5792c6af6abf27ae9c6",
        "checkfunc": tarball_version,
    },
)

build.add(
    "libmd",
    build_func=build_libmd,
    download={
        "url": "https://archive.hadrons.org/software/libmd/libmd-{version}.tar.xz",
        "fallback_url": "https://nexus.oit.gatech.edu/relenv/dependencies/libmd-{version}.tar.gz",
        "version": "1.1.0",
        "checksum": "72718d5ffad112b702ba84fd40900486f8179642",
        "checkfunc": tarball_version,
    },
)

build.add(
    "libbsd",
    build_func=build_libbsd,
    wait_on=[
        "libmd",
    ],
    download={
        "url": "https://libbsd.freedesktop.org/releases/libbsd-{version}.tar.xz",
        "fallback_url": "https://nexus.oit.gatech.edu/relenv/dependencies/libbsd-{version}.tar.gz",
        "version": "0.12.2",
        "checksum": "c8f49920dec71e8e72f2b19f6c209b440a367d3a",
        "checkfunc": tarball_version,
    },
)

build.add(
    "zeromq",
    build_func=build_zeromq,
    wait_on=[
        "libsodium",
        "libbsd"
    ],
    download={
        "url": "https://github.com/zeromq/libzmq/releases/download/v{version}/zeromq-{version}.tar.gz",
        
        "fallback_url": "https://nexus.oit.gatech.edu/relenv/dependencies/zeromq-{version}.tar.gz",
        "version": "4.3.5",
        "checksum": "bdbf686c8a40ba638e21cf74e34dbb425e108500",
        "checkfunc": tarball_version,
    },
)

build.add(
    "python",
    build_func=build_python,
    wait_on=[
        "libyaml",
        "openssl",
        "libxcrypt",
        "XZ",
        "SQLite",
        "bzip2",
        "gdbm",
        "ncurses",
        "libffi",
        "zlib",
        "uuid",
        "krb5",
        "readline",
        "tirpc",
        "openldap",
        "cyrus-sasl",
        "zeromq",
    ],
    download={
        "url": "https://www.python.org/ftp/python/{version}/Python-{version}.tar.xz",
        "fallback_url": "https://woz.io/relenv/dependencies/Python-{version}.tar.xz",
        "version": build.version,
        "checksum": "401e6a504a956c8f0aab76c4f3ad9df601a83eb1",
        "checkfunc": python_version,
        "checkurl": "https://www.python.org/ftp/python/",
    },
)


build.add(
    "relenv-finalize",
    build_func=finalize,
    wait_on=[
        "python",
        "openssl-fips-module",
    ],
)

build = build.copy(
    version="3.11.11", checksum="acf539109b024d3c5f1fc63d6e7f08cd294ba56d"
)
builds.add("linux", builder=build)

build = build.copy(
    version="3.12.8", checksum="8872c7a124c6970833e0bde4f25d6d7d61c6af6e"
)
builds.add("linux", builder=build)

build = build.copy(
    version="3.13.1", checksum="4b0c2a49a848c3c5d611416099636262a0b9090f"
)
builds.add("linux", builder=build)
