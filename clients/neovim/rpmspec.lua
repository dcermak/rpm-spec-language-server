-- RPM Spec files
return {
    cmd = {
        "python3",
        "-mrpm_spec_language_server",
        "--stdio",
        "--verbose",
        "--log_file",
        vim.fn.stdpath("state") .. "/rpm_spec_lsp-log.txt",
    },
    root_markers = { ".git" },
    filetypes = { "spec" }
}
