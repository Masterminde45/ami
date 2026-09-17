pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'ami'

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('pkgdatadir', pkgdatadir)
configure_file(
            input: 'ami.in',
           output: 'ami',
    configuration: conf,
          install: true,
      install_dir: get_option('bindir'),
     install_mode: 'rwxr-xr-x'
)

ami_sources = [
    '__init__.py',
    'main.py',
    'i18n.py'
]

install_data(ami_sources, install_dir: moduledir)

lang_sources = [
    'lang/en.py',
    'lang/no.py'
]

install_data(lang_sources, install_dir: moduledir / 'lang')
