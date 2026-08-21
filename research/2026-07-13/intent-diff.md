# Intent vs Reality

| intent_id | expected truth | observed reality | diff | violated invariant | intent source | supporting observations | status | claim ids |
|---|---|---|---|---|---|---|---|---|
| I1 | 특정 블로그의 글을 모두 합법적으로 확보할 수 있는 경로가 있다 | 공개 네이버 인터페이스만으로는 완전하고 AI 재사용이 허가된 corpus를 만들 수 없다. 저자 제공 원본/서명 inventory가 우선이며 네이버 endpoint 자동화에는 별도 서면 권한이 필요하다. | “모두”는 URL 수집이 아니라 권한이 붙은 canonical set/freshness/asset proof다. | 수집 가능성, 플랫폼 접근, 저작권, 개인정보, 완전성 분리 | 사용자 요청 | O1-O6,O12-O20,O29-O30 | supported with conditions | C10-C16,C26-C30 |
| I2 | 확보한 글로 저자의 사고를 똑같이 복제할 수 있다 | 내부 사고의 동일성은 관찰·검증 불가능하다. 출처가 있는 과거 주장, 시간별 입장, 문체와 제한된 선택 패턴을 모사하는 proxy만 평가 가능하다. | “분신”을 source-grounded observable-behavior proxy로 재정의해야 한다. | 관찰 가능한 텍스트와 내적 사고의 구분 | 사용자 요청 | O21-O25 | supported limitation | C20-C23 |
| I3 | 구현 방식은 하나의 안전한 데이터 lifecycle로 운영 가능하다 | 권한별 버전, 격리, 전체 파생 lineage, 즉시 서비스 차단, verified purge, processor ack, restore tombstone 및 모델 폐기 경로가 있으면 운영 가능하다. | 단일 consent flag나 source 삭제는 lifecycle이 아니다. | 출처·동의·삭제·모델 영향 추적 | 사용자 요청 | O30-O39 | supported with implementation proof pending | C29-C40 |
| I4 | 결과물의 유사성과 안전성을 객관적으로 평가할 수 있다 | 단일 유사도는 불가능하지만 시간 보류 gold에서 retrieval, sentence support, quote, dated stance, abstention, privacy, identity confusion, agency, revocation을 독립 측정할 수 있다. | “똑같음” 점수 대신 다중 release gate가 필요하다. | 평가 지표와 중단 기준 | 사용자 요청 | O21-O28,O31-O34 | supported with target data pending | C21-C25,C31-C35 |
