use cxx_qt_lib::{QGuiApplication, QQmlApplicationEngine, QQuickStyle, QString, QUrl};
use cxx_qt_lib_extras::QApplication;
use std::env;

mod backend {
    include!(concat!(env!("OUT_DIR"), "/backend.rs"));
}

fn main() {
    let mut app = QApplication::new();

    QGuiApplication::set_desktop_file_name(&QString::from("org.midoriai.RadioStudio"));

    if env::var("QT_QUICK_CONTROLS_STYLE").is_err() {
        QQuickStyle::set_style(&QString::from("org.kde.desktop"));
    }

    let mut engine = QQmlApplicationEngine::new();
    if let Some(engine) = engine.as_mut() {
        engine.load(&QUrl::from(
            "qrc:/qt/qml/org/midoriai/radio/src/qml/Main.qml",
        ));
    }

    if let Some(app) = app.as_mut() {
        app.exec();
    }
}
