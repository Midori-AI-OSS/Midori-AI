use cxx_qt_build::{CxxQtBuilder, QmlModule};

fn main() {
    CxxQtBuilder::new_qml_module(
        QmlModule::new("org.midoriai.radio").qml_file("src/qml/Main.qml"),
    )
    .files(["src/backend.rs"])
    .build();
}
