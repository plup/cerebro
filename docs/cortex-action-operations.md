# Cortex Action Operations

When a Cortex job (analyzer or responder) completes, its report can include operations that TheHive executes automatically. Each operation is identified by a `type` field in the JSON payload.

## AddTagToCase

Adds a tag to the case related to the analyzed entity.

| Parameter | Type   | Required |
|-----------|--------|----------|
| `tag`     | String | Yes      |

## AddTagToArtifact

Adds a tag to the observable (artifact) that was analyzed.

| Parameter | Type   | Required |
|-----------|--------|----------|
| `tag`     | String | Yes      |

## AddTagToAlert

Adds a tag to the alert entity.

| Parameter | Type   | Required |
|-----------|--------|----------|
| `tag`     | String | Yes      |

## CreateTask

Creates a new task in the related case.

| Parameter     | Type   | Required |
|---------------|--------|----------|
| `title`       | String | Yes      |
| `description` | String | Yes      |

## AddCustomFields

Sets or creates a custom field on the related case. The `tpe` field is present in the model but is not used during execution; the type is inferred from the custom field definition.

| Parameter | Type                | Required |
|-----------|---------------------|----------|
| `name`    | String              | Yes      |
| `tpe`     | String              | Yes      |
| `value`   | Any valid JSON value | Yes      |

## CloseTask

Marks the related task as completed. Takes no parameters.

## MarkAlertAsRead

Marks the related alert as read. Takes no parameters.

## AddLogToTask

Adds a log entry to the related task.

| Parameter | Type   | Required |
|-----------|--------|----------|
| `content` | String | Yes      |
| `owner`   | String | No       |

## AddArtifactToCase

Creates a new observable in the related case.

| Parameter         | Type            | Required |
|-------------------|-----------------|----------|
| `data`            | String          | Yes      |
| `dataType`        | String          | Yes      |
| `message`         | String          | Yes      |
| `tlp`             | Integer         | No       |
| `ioc`             | Boolean         | No       |
| `sighted`         | Boolean         | No       |
| `ignoreSimilarity`| Boolean         | No       |
| `tags`            | Array of String | No       |

## AssignCase

Assigns the related case to a specific user.

| Parameter | Type   | Required |
|-----------|--------|----------|
| `owner`   | String | Yes      |
