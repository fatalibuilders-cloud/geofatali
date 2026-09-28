/// The shapes the API returns.
///
/// Parsing is deliberately defensive: a field the server has not sent yet must
/// not crash the app on a construction site. Anything genuinely required is
/// read strictly so a malformed response fails loudly in tests rather than
/// silently rendering an empty screen.
library;

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.detail});

  final String message;
  final int? statusCode;
  final Object? detail;

  bool get isAuthFailure => statusCode == 401;

  @override
  String toString() => message;
}

class Session {
  const Session({required this.token, required this.expiresInHours});

  factory Session.fromJson(Map<String, dynamic> json) => Session(
        token: json['access_token'] as String,
        expiresInHours: (json['expires_in_hours'] as num?)?.toInt() ?? 12,
      );

  final String token;
  final int expiresInHours;
}

class Account {
  const Account({
    required this.id,
    required this.email,
    this.name,
    required this.role,
    this.registrationNo,
  });

  factory Account.fromJson(Map<String, dynamic> json) => Account(
        id: json['id'] as String,
        email: json['email'] as String,
        name: json['name'] as String?,
        role: json['role'] as String? ?? 'free',
        registrationNo: json['registration_no'] as String?,
      );

  final String id;
  final String email;
  final String? name;
  final String role;
  final String? registrationNo;

  /// Only a registered engineer may sign an assessment off.
  bool get canApprove => role == 'engineer' || role == 'admin';
}

class Project {
  const Project({
    required this.id,
    required this.name,
    required this.sector,
    required this.designStandard,
    this.clientName,
    this.country,
    this.administrativeArea,
    this.floors,
    required this.status,
    required this.updatedAt,
  });

  factory Project.fromJson(Map<String, dynamic> json) => Project(
        id: json['id'] as String,
        name: json['name'] as String,
        sector: json['sector'] as String? ?? 'buildings_low_rise',
        designStandard: json['design_standard'] as String? ?? 'eurocode',
        clientName: json['client_name'] as String?,
        country: json['country'] as String?,
        administrativeArea: json['administrative_area'] as String?,
        floors: (json['floors'] as num?)?.toInt(),
        status: json['status'] as String? ?? 'draft',
        updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
            DateTime.now(),
      );

  final String id;
  final String name;
  final String sector;
  final String designStandard;
  final String? clientName;
  final String? country;
  final String? administrativeArea;
  final int? floors;
  final String status;
  final DateTime updatedAt;

  String get location => [administrativeArea, country]
      .where((p) => p != null && p.isNotEmpty)
      .join(', ');
}

class Sector {
  const Sector({
    required this.id,
    required this.label,
    required this.summary,
    required this.governingChecks,
    required this.requiredInvestigation,
    this.note,
  });

  factory Sector.fromJson(Map<String, dynamic> json) => Sector(
        id: json['id'] as String,
        label: json['label'] as String,
        summary: json['summary'] as String? ?? '',
        governingChecks: [
          for (final c in (json['governing_checks'] as List? ?? []))
            GoverningCheck.fromJson(c as Map<String, dynamic>),
        ],
        requiredInvestigation: [
          for (final i in (json['required_investigation'] as List? ?? []))
            i as String,
        ],
        note: (json['note'] as String?)?.isEmpty ?? true ? null : json['note'] as String?,
      );

  final String id;
  final String label;
  final String summary;
  final List<GoverningCheck> governingChecks;
  final List<String> requiredInvestigation;
  final String? note;
}

class GoverningCheck {
  const GoverningCheck({required this.id, required this.label, required this.why});

  factory GoverningCheck.fromJson(Map<String, dynamic> json) => GoverningCheck(
        id: json['id'] as String,
        label: json['label'] as String,
        why: json['why'] as String? ?? '',
      );

  final String id;
  final String label;
  final String why;
}

class Borehole {
  const Borehole({
    required this.id,
    required this.code,
    this.totalDepthM,
    this.groundwaterDepthM,
    required this.groundwaterObserved,
    this.drillingMethod,
  });

  factory Borehole.fromJson(Map<String, dynamic> json) => Borehole(
        id: json['id'] as String,
        code: json['code'] as String,
        totalDepthM: (json['total_depth_m'] as num?)?.toDouble(),
        groundwaterDepthM: (json['groundwater_depth_m'] as num?)?.toDouble(),
        groundwaterObserved: json['groundwater_observed'] as bool? ?? false,
        drillingMethod: json['drilling_method'] as String?,
      );

  final String id;
  final String code;
  final double? totalDepthM;
  final double? groundwaterDepthM;
  final bool groundwaterObserved;
  final String? drillingMethod;
}

class SoilLayer {
  const SoilLayer({
    required this.id,
    required this.topDepthM,
    required this.bottomDepthM,
    this.description,
    this.uscsClass,
    this.confidence,
    required this.classificationSource,
  });

  factory SoilLayer.fromJson(Map<String, dynamic> json) => SoilLayer(
        id: json['id'] as String,
        topDepthM: (json['top_depth_m'] as num).toDouble(),
        bottomDepthM: (json['bottom_depth_m'] as num).toDouble(),
        description: json['description'] as String?,
        uscsClass: json['uscs_class'] as String?,
        confidence: (json['confidence'] as num?)?.toDouble(),
        classificationSource: json['classification_source'] as String,
      );

  final String id;
  final double topDepthM;
  final double bottomDepthM;
  final String? description;
  final String? uscsClass;
  final double? confidence;
  final String classificationSource;

  double get thicknessM => bottomDepthM - topDepthM;

  /// Whether this layer's class was measured, or merely observed.
  bool get isMeasured =>
      classificationSource == 'LABORATORY' || classificationSource == 'FIELD';
}

class EngineWarning {
  const EngineWarning({required this.severity, required this.code, required this.message});

  factory EngineWarning.fromJson(Map<String, dynamic> json) => EngineWarning(
        severity: json['severity'] as String? ?? 'INFO',
        code: json['code'] as String? ?? '',
        message: json['message'] as String? ?? '',
      );

  final String severity;
  final String code;
  final String message;

  bool get isCritical => severity == 'CRITICAL';
}

class CalculationResult {
  const CalculationResult({
    required this.id,
    required this.calculationType,
    required this.method,
    required this.status,
    required this.preliminary,
    required this.results,
    required this.warnings,
    this.standard,
    this.engineVersion,
  });

  factory CalculationResult.fromJson(Map<String, dynamic> json) => CalculationResult(
        id: json['id'] as String? ?? '',
        calculationType: json['calculation_type'] as String? ?? '',
        method: json['method'] as String? ?? '',
        status: json['status'] as String? ?? '',
        preliminary: json['preliminary'] as bool? ?? true,
        results: (json['results'] as Map?)?.cast<String, dynamic>() ?? {},
        warnings: [
          for (final w in (json['warnings'] as List? ?? []))
            EngineWarning.fromJson(w as Map<String, dynamic>),
        ],
        standard: json['standard'] as String?,
        engineVersion: json['engine_version'] as String?,
      );

  final String id;
  final String calculationType;
  final String method;
  final String status;
  final bool preliminary;
  final Map<String, dynamic> results;
  final List<EngineWarning> warnings;
  final String? standard;
  final String? engineVersion;

  /// The engine refused because a required input was missing.
  bool get isRefusal => status == 'INSUFFICIENT_DATA';

  double? get netAllowableKpa =>
      (results['net_allowable_capacity_kpa'] as num?)?.toDouble();
  double? get ultimateKpa =>
      (results['ultimate_capacity_kpa'] as num?)?.toDouble();
}

class Criterion {
  const Criterion({required this.name, required this.verdict, required this.evidence});

  factory Criterion.fromJson(Map<String, dynamic> json) => Criterion(
        name: json['name'] as String,
        verdict: json['verdict'] as String,
        evidence: json['evidence'] as String? ?? '',
      );

  final String name;
  final String verdict;
  final String evidence;
}

class ConstructionStep {
  const ConstructionStep({
    required this.order,
    required this.title,
    required this.detail,
    required this.holdPoint,
    this.verify,
    this.triggeredBy,
  });

  factory ConstructionStep.fromJson(Map<String, dynamic> json) => ConstructionStep(
        order: (json['order'] as num).toInt(),
        title: json['title'] as String,
        detail: json['detail'] as String? ?? '',
        holdPoint: json['hold_point'] as bool? ?? false,
        verify: json['verify'] as String?,
        triggeredBy: json['triggered_by'] as String?,
      );

  final int order;
  final String title;
  final String detail;
  final bool holdPoint;
  final String? verify;

  /// Set when this step exists because of what the investigation found here,
  /// rather than being part of the standard sequence.
  final String? triggeredBy;
}

class FoundationCandidate {
  const FoundationCandidate({
    required this.foundationType,
    required this.label,
    required this.status,
    required this.criteria,
    required this.rationale,
    required this.conditions,
    required this.missingData,
    required this.relativeCost,
    required this.steps,
    this.id,
  });

  factory FoundationCandidate.fromJson(Map<String, dynamic> json) => FoundationCandidate(
        foundationType: json['foundation_type'] as String,
        label: json['label'] as String,
        status: json['status'] as String,
        criteria: [
          for (final c in (json['criteria'] as List? ?? []))
            Criterion.fromJson(c as Map<String, dynamic>),
        ],
        rationale: [for (final r in (json['rationale'] as List? ?? [])) r as String],
        conditions: [for (final c in (json['conditions'] as List? ?? [])) c as String],
        missingData: [for (final m in (json['missing_data'] as List? ?? [])) m as String],
        relativeCost: json['relative_cost'] as String? ?? 'moderate',
        steps: [
          for (final s in (json['construction_steps'] as List? ?? []))
            ConstructionStep.fromJson(s as Map<String, dynamic>),
        ],
      );

  final String foundationType;
  final String label;
  final String status;
  final List<Criterion> criteria;
  final List<String> rationale;
  final List<String> conditions;
  final List<String> missingData;
  final String relativeCost;
  final List<ConstructionStep> steps;
  final String? id;

  String get statusLabel => switch (status) {
        'PRELIMINARY_CANDIDATE' => 'Candidate',
        'CANDIDATE_WITH_CONDITIONS' => 'Candidate, with conditions',
        'NOT_RECOMMENDED' => 'Not recommended as found',
        'REQUIRES_DATA' => 'Needs more data',
        _ => status,
      };

  int get failures => criteria.where((c) => c.verdict == 'FAIL').length;
}
