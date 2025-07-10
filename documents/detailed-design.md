# 映画館窓口業務エージェント - 詳細設計書

## 1. 概要
本文書は映画館窓口業務エージェントのMCPツール群の詳細設計を記述する。
各機能の処理フロー、データアクセス方法、バリデーション、エラーハンドリングを定義する。

## 2. 前提条件
- データソース: Azure Filesのmovie-agent-data配下のJSONファイル
- 予約データ保存: Azure Filesのmovie-agent-data/reservations.jsonl（JSON Lines形式）
- リクエストパラメータには最低限のバリデーションを実装
- エラー時は適切なエラーメッセージと共にHTTP相当のステータスを返却

## 3. 共通仕様

### 3.1 起動時処理
- src/data配下のjsonファイル群をAzure Filesのmovie-agent-dataファイル共有にアップロードする（既存ファイルがある場合は上書きする）

### 3.2 データファイル
- movies.json: 映画マスタデータ
- schedules.json: 上映スケジュールデータ
- seat_availability.json: 座席状況データ
- reservations.jsonl: 予約データ（追記形式）

### 3.3 共通バリデーション
- 日付形式: YYYY-MM-DD（正規表現: ^\d{4}-\d{2}-\d{2}$）
- 時刻形式: HH:MM（正規表現: ^\d{2}:\d{2}$）
- 必須パラメータの存在チェック
- 文字列長制限チェック

### 3.4 エラーハンドリング
- データファイル読み込みエラー
- パラメータバリデーションエラー
- データ不整合エラー
- 予約競合エラー

## 4. 各機能の詳細設計

### 4.1 映画一覧取得機能（get_movie_list）

#### 4.1.1 機能概要
現在上映中の映画一覧を取得し、オプションでフィルタリングを行う。

#### 4.1.2 処理フロー
1. **パラメータバリデーション**
   - date: 日付形式チェック（YYYY-MM-DD）
   - search_query: 文字列長チェック（最大100文字）
   - genre: 文字列長チェック（最大50文字）

2. **データ読み込み**
   - movie-agent-data/movies.json を読み込み
   - ファイル存在・フォーマットチェック

3. **データフィルタリング**
   - dateパラメータが指定されている場合:
     - movie-agent-data/schedules.json を読み込み
     - 指定日に上映スケジュールが存在する映画のみ抽出
   - search_queryが指定されている場合:
     - 映画タイトルの部分一致検索（大文字小文字区別なし）
   - genreが指定されている場合:
     - ジャンルの完全一致検索

4. **レスポンス生成**
   - フィルタ結果をJSON形式で返却
   - 映画データの全フィールドを含む

#### 4.1.3 エラーハンドリング
- 日付形式不正: "Invalid date format. Use YYYY-MM-DD."
- データファイル読み込み失敗: "Failed to load movie data."
- 検索結果なし: 空の配列を返却（エラーではない）

### 4.2 上映スケジュール取得機能（get_show_schedule）

#### 4.2.1 機能概要
特定日の上映スケジュールを取得し、座席空き状況のサマリーも併せて返却する。
映画をIDやタイトルによって絞り込みも可能。

#### 4.2.2 処理フロー
1. **パラメータバリデーション**
   - movie_id: 文字列長チェック（最大20文字）
   - date: 必須、日付形式チェック（YYYY-MM-DD）
   - movie_title: movie_idの代替として使用可能

2. **映画IDの解決**
   - movie_titleが指定されている場合:
     - movie-agent-data/movies.json から該当映画を検索
     - movie_idを特定

3. **スケジュールデータ読み込み**
   - movie-agent-data/schedules.json を読み込み
   - date（およびmovie_idが絞り込まれている場合のみmovie_idとも）一致するスケジュールを抽出

4. **座席状況サマリー計算**
   - movie-agent-data/seat_availability.json を読み込み
   - 各スケジュールIDについて:
     - available_seatsの総数を計算
     - occupied_seatsの総数を計算
     - total_seats_count = available + occupied

5. **レスポンス生成**
   - スケジュール情報と座席サマリーを統合
   - 時刻順でソート

#### 4.2.3 エラーハンドリング
- 映画が見つからない: "Movie not found."
- 日付形式不正: "Invalid date format. Use YYYY-MM-DD."
- スケジュールなし: 空の配列を返却

### 4.3 座席空き状況取得機能（get_seat_availability）

#### 4.3.1 機能概要
指定したスケジュールIDの詳細座席状況を取得する。

#### 4.3.2 処理フロー
1. **パラメータバリデーション**
   - schedule_id: 必須、文字列長チェック（最大20文字）

2. **スケジュール存在確認**
   - movie-agent-data/schedules.json でschedule_idの存在確認
   - 存在しない場合はエラー

3. **映画情報取得**
   - スケジュールデータからmovie_idを取得
   - movie-agent-data/movies.json からmovie_idに対応する映画情報を取得

4. **座席状況データ読み込み**
   - movie-agent-data/seat_availability.json からschedule_idに対応するデータを取得

5. **レスポンス生成**
   - schedule_info, available_seats, occupied_seatsを統合
   - 行はアルファベット順、座席番号は昇順でソート

#### 4.3.3 エラーハンドリング
- schedule_id未指定: "schedule_id is required."
- スケジュールが見つからない: "Schedule not found."
- 座席データなし: "Seat data not available."

### 4.4 座席予約機能（reserve_seats）

#### 4.4.1 機能概要
指定した座席の予約を実行し、予約データを永続化する。

#### 4.4.2 処理フロー
1. **パラメータバリデーション**
   - schedule_id: 必須、文字列長チェック（最大20文字）
   - seat_ids: 必須、文字列、カンマ区切りの座席ID（例: "A1,B2,D4"）、最大100文字
   - カンマ区切り文字列をパース後、各座席ID形式チェック: ^[A-Z]\d+$

2. **スケジュール存在確認**
   - movie-agent-data/schedules.json でschedule_idの存在確認
   - 対応する映画情報も同時に取得

3. **座席空き状況確認**
   - movie-agent-data/seat_availability.json から現在の座席状況を読み込み
   - 指定された全座席が利用可能かチェック

4. **予約データ生成**
   - 一意の予約ID生成（RES + タイムスタンプ + 連番）
   - 予約時刻取得（ISO 8601形式）
   - 予約ステータス設定（"confirmed"）

5. **座席状況更新**
   - 予約対象座席をavailable_seatsからoccupied_seatsに移動
   - movie-agent-data/seat_availability.json を更新

6. **予約データ保存**
   - 予約データをmovie-agent-data/reservations.jsonl に追記
   - JSON Lines形式（1行1予約）

7. **レスポンス生成**
   - 予約情報、スケジュール情報、成功メッセージを返却

#### 4.4.3 エラーハンドリング
- スケジュールが見つからない: "Schedule not found."
- 座席ID形式不正: "Invalid seat ID format."
- 座席が既に予約済み: "Seat [座席ID] is already occupied."
- データ更新失敗: "Failed to save reservation data."

#### 4.4.4 トランザクション制御
- 座席状況更新と予約データ保存は原子性を保つ
- いずれかが失敗した場合は全処理をロールバック

### 4.5 予約詳細確認機能（get_reservation_details）

#### 4.5.1 機能概要
予約IDを指定して予約の詳細情報を取得する。

#### 4.5.2 処理フロー
1. **パラメータバリデーション**
   - reservation_id: 必須、文字列長チェック（最大30文字）

2. **予約データ検索**
   - movie-agent-data/reservations.jsonl を読み込み
   - reservation_idに一致する予約を検索

3. **関連データ取得**
   - スケジュール情報: movie-agent-data/schedules.json
   - 映画情報: movie-agent-data/movies.json

4. **座席詳細情報生成**
   - 座席IDを行と番号に分解

5. **レスポンス生成**
   - 予約情報、スケジュール情報、座席詳細を統合

#### 4.5.3 エラーハンドリング
- 予約IDが見つからない: "Reservation not found."
- 関連データ不整合: "Data inconsistency detected."

## 5. データ整合性

### 5.1 座席状況の整合性
- available_seatsとoccupied_seatsの重複チェック
- 総座席数の一貫性チェック（各劇場16席）

### 5.2 予約データの整合性
- 予約された座席がoccupied_seatsに反映されているかチェック
- 同一座席の重複予約防止

### 5.3 スケジュールデータの整合性
- 映画の上映時間とスケジュールの終了時間の整合性
- 同一劇場での時間重複チェック

## 6. パフォーマンス考慮事項

### 6.1 データキャッシュ
- 映画データとスケジュールデータはメモリキャッシュ推奨
- 座席状況データは常に最新を読み込み

### 6.2 ファイルI/O最適化
- JSON Linesファイルの読み込み最適化
- 大量予約データに対する効率的な検索

## 7. セキュリティ考慮事項

### 7.1 入力値検証
- SQLインジェクション対策（該当しないが安全な文字列処理）
- パス traversal 攻撃防止
- 過度に長い文字列の制限

### 7.2 ファイルアクセス制御
- src/dataおよびAzure Filesのmovie-agent-data配下のみアクセス許可
- 設定ファイルや実行ファイルへのアクセス禁止

## 8. ログ・監査

### 8.1 予約操作ログ
- 全予約操作をタイムスタンプ付きで記録
- 座席状況変更の監査証跡

### 8.2 エラーログ
- システムエラー、バリデーションエラーの記録
- デバッグ用詳細情報の出力
