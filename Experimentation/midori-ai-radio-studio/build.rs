use cxx_qt_build::{CxxQtBuilder, QmlModule};
use std::{env, fs, path::PathBuf};

const SEARCH_TEXT_OLD: &str = r#"    let search_text = [
        &title,
        &artist,
        &album,
        &genre,
        &comment,
        &why_made,
        &backstory,
        &radio_reason,
        &music_theme,
        &listener_takeaway,
        &vibe_summary,
        &file_name,
        &channel,
    ]"#;

const SEARCH_TEXT_NEW: &str = r#"    let search_text = [
        title.as_str(),
        artist.as_str(),
        album.as_str(),
        genre.as_str(),
        comment.as_str(),
        why_made.as_str(),
        backstory.as_str(),
        radio_reason.as_str(),
        music_theme.as_str(),
        listener_takeaway.as_str(),
        vibe_summary.as_str(),
        file_name.as_str(),
        channel.as_str(),
    ]"#;

fn main() {
    println!("cargo:rerun-if-changed=src/backend.rs");
    println!("cargo:rerun-if-changed=src/qml/Main.qml");

    let backend_source = fs::read_to_string("src/backend.rs")
        .expect("failed to read src/backend.rs");
    let replacement_count = backend_source.matches(SEARCH_TEXT_OLD).count();
    assert_eq!(
        replacement_count, 1,
        "expected exactly one search-text coercion block, found {replacement_count}"
    );

    let generated_backend = backend_source.replacen(SEARCH_TEXT_OLD, SEARCH_TEXT_NEW, 1);
    let generated_path = PathBuf::from(env::var_os("OUT_DIR").expect("OUT_DIR is not set"))
        .join("backend.rs");
    fs::write(&generated_path, generated_backend)
        .expect("failed to write generated backend.rs");

    CxxQtBuilder::new_qml_module(
        QmlModule::new("org.midoriai.radio").qml_file("src/qml/Main.qml"),
    )
    .files([generated_path])
    .build();
}
