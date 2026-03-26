/**
 * EKT(전자공탁) 파일 다운로드 프록시
 *
 * 배경: ekt.scourt.go.kr/pjg/pjgedm/blobDown.on 은 JSON POST 전용이라
 * 브라우저에서 직접 GET URL로 파일을 받을 수 없음.
 * 이 Route Handler가 GET 요청을 받아 내부적으로 POST로 변환 후 파일 스트림을 반환한다.
 *
 * 요청 형태: GET /api/ekt-download?dvsCd=22&ext=hwp
 */

import { NextRequest, NextResponse } from "next/server";

const EKT_DOWNLOAD_BASE = "https://ekt.scourt.go.kr/pjg/pjgedm/blobDown.on";
const EKT_REFERER = "https://ekt.scourt.go.kr/pjg/index.on?m=PJG172M03";

const FILE_COL: Record<string, string> = {
  hwp: "dpsHwpFrmlFile",
  doc: "dpsDocxFrmlFile",
  pdf: "dpsPdfFrmlFile",
  gif: "dpsWrtExmFile",
};

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const dvsCd = searchParams.get("dvsCd") ?? "";
  const ext = searchParams.get("ext") ?? "";
  const fileCol = FILE_COL[ext] ?? "";

  if (!dvsCd || !ext || !fileCol) {
    return NextResponse.json(
      { error: "dvsCd, ext 파라미터 필요 (ext: hwp|doc|pdf|gif)" },
      { status: 400 }
    );
  }

  // EKT 서버는 Referer 세션 쿠키가 필요 — 먼저 Referer 페이지를 GET해서 쿠키 획득
  let cookie = "";
  try {
    const refResp = await fetch(EKT_REFERER, {
      headers: { "User-Agent": "Mozilla/5.0" },
      redirect: "follow",
    });
    const setCookie = refResp.headers.get("set-cookie");
    if (setCookie) {
      cookie = setCookie
        .split(",")
        .map((c) => c.split(";")[0].trim())
        .join("; ");
    }
  } catch {
    // 쿠키 획득 실패해도 POST 시도는 계속
  }

  let ektResp: Response;
  try {
    ektResp = await fetch(EKT_DOWNLOAD_BASE, {
      method: "POST",
      headers: {
        "Content-Type": "application/json; charset=UTF-8",
        Referer: EKT_REFERER,
        "User-Agent": "Mozilla/5.0",
        ...(cookie ? { Cookie: cookie } : {}),
      },
      body: JSON.stringify({
        dma_downloadFile: {
          kindCode: "03",
          dpsFrmlDvsCd: dvsCd,
          fileExtsPnlim: ext,
          fileColumn: fileCol,
          fileNm: "dpsFrmlFileNm",
        },
      }),
    });
  } catch (e) {
    return NextResponse.json({ error: `EKT 서버 연결 실패: ${e}` }, { status: 502 });
  }

  if (!ektResp.ok) {
    return NextResponse.json(
      { error: `EKT 서버 오류: ${ektResp.status}` },
      { status: 502 }
    );
  }

  const buf = await ektResp.arrayBuffer();
  if (buf.byteLength < 100) {
    return NextResponse.json({ error: "EKT 서버가 빈 응답 반환" }, { status: 502 });
  }

  const cd =
    ektResp.headers.get("content-disposition") ??
    `attachment; filename="form_${dvsCd}.${ext}"`;

  return new NextResponse(buf, {
    status: 200,
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": cd,
      "Content-Length": String(buf.byteLength),
    },
  });
}
