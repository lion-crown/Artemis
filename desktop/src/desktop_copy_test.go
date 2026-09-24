package main

import "testing"

func TestDesktopTextLooksUpLocaleWithEnglishDefault(t *testing.T) {
	if got := desktopText(LocaleZH, copyStatusReady); got != "Artemis 已就绪" {
		t.Fatalf("zh: %s", got)
	}
	if got := desktopText(LocaleEN, copyStatusReady); got != "Artemis is ready" {
		t.Fatalf("en: %s", got)
	}
	if got := desktopText(Locale(""), copyStatusReady); got != "Artemis is ready" {
		t.Fatalf("unknown locale should fall back to English: %s", got)
	}
	if got := desktopText(LocaleZH, copyStatusConnecting); got != "正在连接 Artemis…" {
		t.Fatalf("zh connection: %s", got)
	}
	if got := desktopText(LocaleEN, copyStatusConnecting); got != "Connecting to Artemis…" {
		t.Fatalf("en connection: %s", got)
	}
	if got := desktopText(LocaleZH, copyHealthNotReady); got != "Artemis 服务未在%s内就绪（%s）。请确认本机已启动 Artemis，且地址、端口正确；也可查看终端日志。" {
		t.Fatalf("zh health error: %s", got)
	}
	if got := desktopText(LocaleEN, copyHealthNotReady); got != "Artemis did not become ready within %s (%s). Make sure Artemis is running at this address, or check the terminal logs." {
		t.Fatalf("en health error: %s", got)
	}
	if got := desktopText(LocaleZH, "missing.key"); got != "missing.key" {
		t.Fatalf("unknown key: %s", got)
	}
}

func TestDesktopTextFormatsArgs(t *testing.T) {
	got := desktopText(LocaleEN, copyStatusBackupDatabase, "0.9.32")
	if got != "Desktop update 0.9.32 found. Backing up the database…" {
		t.Fatalf("format: %s", got)
	}
}
