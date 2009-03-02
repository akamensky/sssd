AC_DEFUN(WITH_DB_PATH,
  [ AC_ARG_WITH([db-path],
                [AC_HELP_STRING([--with-db-path=PATH],
                                [Path to the SSSD databases [/var/lib/sss/db]]
                               )
                ]
               )
    dbpath="/var/lib/sss/db"
    if test x"$with_db_path" != x; then
        dbpath=$with_db_path
    fi
    AC_SUBST(dbpath)
    AC_DEFINE_UNQUOTED(DB_PATH, "$dbpath", [Path to the SSSD databases])
  ])

AC_DEFUN(WITH_PLUGIN_PATH,
  [ AC_ARG_WITH([plugin-path],
                [AC_HELP_STRING([--with-plugin-path=PATH],
                                [Path to the SSSD data provider plugins [/usr/lib/sssd]]
                               )
                ]
               )
    pluginpath="/usr/lib/sssd"
    if test x"$with_plugin_path" != x; then
        pluginpath=$with_plugin_path
    fi
    AC_SUBST(pluginpath)
    AC_DEFINE_UNQUOTED(DATA_PROVIDER_PLUGINS_PATH, "$pluginpath", [Path to the SSSD data provider plugins])
  ])

AC_DEFUN(WITH_PID_PATH,
  [ AC_ARG_WITH([pid-path],
                [AC_HELP_STRING([--with-pid-path=PATH],
                                [Where to store pid files for the SSSD [/var/run]]
                               )
                ]
               )
    pidpath="/var/run"
    if test x"$with_pid_path" != x; then
        pidpath=$with_pid_path
    fi
    AC_SUBST(pidpath)
    AC_DEFINE_UNQUOTED(PID_PATH, "$pidpath", [Where to store pid files for the SSSD])
  ])

AC_DEFUN(WITH_PIPE_PATH,
  [ AC_ARG_WITH([pipe-path],
                [AC_HELP_STRING([--with-pipe-path=PATH],
                                [Where to store pipe files for the SSSD interconnects [/var/lib/sss/pipes]]
                               )
                ]
               )
    pipepath="/var/lib/sss/pipes"
    if test x"$with_pipe_path" != x; then
        pipepath=$with_pipe_path
    fi
    AC_SUBST(pipepath)
    AC_DEFINE_UNQUOTED(PIPE_PATH, "$pipepath", [Where to store pipe files for the SSSD interconnects])
  ])

AC_DEFUN(WITH_POLICYKIT,
  [ AC_ARG_WITH([policykit],
                [AC_HELP_STRING([--with-policykit],
                                [Whether to include PolicyKit support [yes]]
                               )
                ],
                [],
                with_policykit=yes
               )
    if test x"$with_policykit" == xyes; then
        AC_DEFINE(HAVE_POLICYKIT, 1, [Include PolicyKit support])
        HAVE_POLICYKIT=1
        AC_SUBST(HAVE_POLICYKIT)
    fi
  ])

AC_DEFUN(WITH_INFOPIPE,
  [ AC_ARG_WITH([infopipe],
                [AC_HELP_STRING([--with-infopipe],
                                [Whether to include InfoPipe support [yes]]
                               )
                ],
                [],
                with_infopipe=yes
               )
    if test x"$with_infopipe" == xyes; then
        AC_DEFINE(HAVE_INFOPIPE, 1, [Include InfoPipe support])
        HAVE_INFOPIPE=1
        AC_SUBST(HAVE_INFOPIPE)
    fi
  ])

AC_DEFUN(WITH_TESTS,
  [ AC_ARG_WITH([tests],
                [AC_HELP_STRING([--with-tests],
                                [Whether to build tests [no]]
                               )
                ],
                [],
                with_tests=no
               )

    if test x"$with_tests" == xyes; then
        AC_DEFINE(HAVE_TESTS, 1, [Build tests])
        HAVE_TESTS=1
        AC_SUBST(HAVE_TESTS)
    fi
  ])

