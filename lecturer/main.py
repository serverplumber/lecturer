from pathlib import Path

from cement import App

from lecturer.controllers import HANDLERS


class Lecturer(App):
    class Meta:
        label = "lecturer"
        base_controller = "base"
        handlers = HANDLERS
        exit_on_close = True


# A repo-local, gitignored config file, checked for by main() below — lets a
# dev checkout keep its own settings (an in-repo elocution_dir, say) without
# writing to ~/.config/lecturer/lecturer.conf, which an installed copy on the
# same machine would also read. Not registered in Lecturer.Meta.config_files:
# Cement loads the user-level ~/.config file *after* anything named there
# (core_user_config_files always comes last), so listing it that way would
# have the installed location win instead of this one. Parsed explicitly
# after Cement's own setup so it merges in with the final say instead.
_DEV_CONFIG = Path(__file__).resolve().parent.parent / "lecturer.conf"


def main():
    with Lecturer() as app:
        if _DEV_CONFIG.exists():
            app.config.parse_file(str(_DEV_CONFIG))
        app.run()


if __name__ == "__main__":
    main()
