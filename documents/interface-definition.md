# 映画館窓口業務エージェント - インタフェース仕様書

## 1. 概要
映画館窓口業務を行うエージェントのMCP（Model Context Protocol）ツール群の仕様を定義する。
本仕様書は要件定義書（documents/requirements.txt）および業務シナリオ（documents/operation-scenario.txt）に基づいて作成されている。

## 2. MCPツール仕様

### 2.1 映画一覧取得ツール

**ツール名**: `get_movie_list`

**説明**: 現在上映中の映画一覧を取得する。日付指定による絞り込みや映画名の部分検索が可能。

**JSON-RPC仕様**:
```json
{
  "name": "get_movie_list",
  "description": "Get a list of currently showing movies. Supports filtering by date and partial search by movie title.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "date": {
        "type": "string",
        "description": "Screening date in YYYY-MM-DD format. If not specified, returns all currently showing movies",
        "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
      },
      "search_query": {
        "type": "string",
        "description": "Keyword for partial movie title search"
      },
      "genre": {
        "type": "string",
        "description": "Filter by genre"
      }
    },
    "required": []
  }
}
```

**レスポンス構造**:
```json
{
  "movies": [
    {
      "movie_id": "string",
      "title": "string",
      "genre": "string",
      "duration": "number",
      "rating": "number",
      "description": "string",
      "release_date": "string"
    }
  ]
}
```

### 2.2 上映スケジュール取得ツール

**ツール名**: `get_show_schedule`

**説明**: 指定した日の上映スケジュールを取得する。映画をIDやタイトルによって絞り込みも可能。空席有無も併せて返却。

**JSON-RPC仕様**:
```json
{
  "name": "get_show_schedule",
  "description": "Get screening schedule for a specified movie. Also returns seat availability information.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "movie_id": {
        "type": "string",
        "description": "Movie ID"
      },
      "movie_title": {
        "type": "string",
        "description": "Movie title (can be used as alternative to movie_id)"
      },
      "date": {
        "type": "string",
        "description": "Screening date in YYYY-MM-DD format",
        "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
      }
    },
    "required": ["date"]
  }
}
```

**レスポンス構造**:
```json
{
  "schedules": [
    {
      "schedule_id": "string",
      "movie_id": "string",
      "date": "string",
      "start_time": "string",
      "end_time": "string",
      "theater_id": "string",
      "movie_title": "string",
      "available_seats_count": "number",
      "total_seats_count": "number"
    }
  ]
}
```

### 2.3 座席空き状況取得ツール

**ツール名**: `get_seat_availability`

**説明**: 指定した上映回の詳細な座席空き状況を取得する。

**JSON-RPC仕様**:
```json
{
  "name": "get_seat_availability",
  "description": "Get detailed seat availability for a specified screening session.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "schedule_id": {
        "type": "string",
        "description": "Schedule ID you want to get the list of available seats"
      }
    },
    "required": ["schedule_id"]
  }
}
```

**レスポンス構造**:
```json
{
  "schedule_info": {
    "schedule_id": "string",
    "movie_id": "string",
    "date": "string",
    "start_time": "string",
    "end_time": "string",
    "theater_id": "string",
    "movie_title": "string"
  },
  "available_seats": [
    {
      "row": "string",
      "available_numbers": ["number"]
    }
  ],
  "occupied_seats": [
    {
      "row": "string",
      "occupied_numbers": ["number"]
    }
  ]
}
```

### 2.4 座席予約ツール

**ツール名**: `reserve_seats`

**説明**: 指定した座席の予約を実行する。複数座席の同時予約に対応。

**JSON-RPC仕様**:
```json
{
  "name": "reserve_seats",
  "description": "Reserve specified seats. Supports multiple seat reservations simultaneously.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "schedule_id": {
        "type": "string",
        "description": "Schedule ID"
      },
      "seat_ids": {
        "type": "string",
        "description": "Comma-separated list of seat IDs to reserve (e.g., 'A1,B2,D4')"
      }
    },
    "required": ["schedule_id", "seat_ids"]
  }
}
```

**レスポンス構造**:
```json
{
  "reservation": {
    "reservation_id": "string",
    "schedule_id": "string",
    "seat_ids": ["string"],
    "reservation_time": "string",
    "status": "string"
  },
  "schedule_info": {
    "movie_id": "string",
    "movie_title": "string",
    "date": "string",
    "start_time": "string",
    "end_time": "string",
    "theater_id": "string"
  },
  "message": "string"
}
```

### 2.5 予約詳細確認ツール

**ツール名**: `get_reservation_details`

**説明**: 予約IDを指定して予約の詳細情報を取得する。

**JSON-RPC仕様**:
```json
{
  "name": "get_reservation_details",
  "description": "Get detailed information for a reservation by reservation ID.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "reservation_id": {
        "type": "string",
        "description": "Reservation ID"
      }
    },
    "required": ["reservation_id"]
  }
}
```

**レスポンス構造**:
```json
{
  "reservation": {
    "reservation_id": "string",
    "schedule_id": "string",
    "seat_ids": ["string"],
    "reservation_time": "string",
    "status": "string"
  },
  "schedule_info": {
    "movie_id": "string",
    "movie_title": "string",
    "date": "string",
    "start_time": "string",
    "end_time": "string",
    "theater_id": "string"
  },
  "seat_details": [
    {
      "seat_id": "string",
      "row": "string",
      "number": "number"
    }
  ]
}
```
